# Guarded reload of the EXISTING owner-paired native WSS relay (port 8995).
# Never changes pairing, SSH, tokens, Android data, Gateway retirement or worker.
param([switch]$Apply)
$ErrorActionPreference='Stop'
# Run only as detached maintenance after originating native pc_command exits.
if($Apply){Start-Sleep -Seconds 8}
$root='D:\AsterionControlRelease'
$state=Join-Path $env:LOCALAPPDATA 'AsterionControl'
$report=Join-Path $state 'v6-native-wss-reload.json'
function Save-Receipt([string]$phase,[bool]$ok,[string]$reason,[hashtable]$details){
  $value=[ordered]@{phase=$phase;ok=$ok;reason=$reason;observed_at=(Get-Date -Format o)}
  foreach($k in $details.Keys){$value[$k]=$details[$k]}
  $temp=$report+'.new'
  [IO.File]::WriteAllText($temp,($value|ConvertTo-Json -Depth 5 -Compress),(New-Object System.Text.UTF8Encoding($false)))
  Move-Item -LiteralPath $temp -Destination $report -Force
}
function Rpc-Status {
  try{
    [void](Invoke-WebRequest 'http://127.0.0.1:8995/phone/rpc' -Method Get -UseBasicParsing -TimeoutSec 2)
    return 200
  }catch{
    if($_.Exception.Response){return [int]$_.Exception.Response.StatusCode}
    return 0
  }
}
function Native-Health {
  try{
    $r=Invoke-RestMethod 'http://127.0.0.1:8995/healthz' -TimeoutSec 2
    if($r.ok -and $r.service -eq 'asterion-native-phone-wss'){return $r}
  }catch{}
  return $null
}
try{
  foreach($p in @((Join-Path $root '.venv\Scripts\python.exe'),(Join-Path $root 'asterion_remote\native_phone_relay.py'),(Join-Path $root 'asterion_remote\native_phone_rpc.py'))){
    if(-not(Test-Path -LiteralPath $p)){throw 'Original native relay runtime missing'}
  }
  if(-not([IO.File]::ReadAllText((Join-Path $root 'asterion_remote\native_phone_relay.py'))).Contains('local_rpc_router')){
    throw 'Existing native relay source missing RPC router'
  }
  if(-not([IO.File]::ReadAllText((Join-Path $root 'asterion_remote\native_phone_rpc.py'))).Contains('/phone/rpc')){
    throw 'Original native RPC route implementation missing'
  }
  $current=Native-Health
  $route=Rpc-Status
  if($current -and $route -eq 405){
    Save-Receipt 'already_operational' $true 'Existing RPC route responds' @{rpc_http=$route;phone_connected=([bool]$current.phone_connected)}
    exit 0
  }
  $ports=@(Get-NetTCPConnection -LocalPort 8995 -State Listen -ErrorAction Stop)
  if($ports.Count -ne 1){throw 'Native WSS listener count unexpected'}
  $pidBefore=[int]$ports[0].OwningProcess
  $owner=Get-CimInstance Win32_Process -Filter ('ProcessId='+$pidBefore) -ErrorAction Stop
  if(-not $owner -or $owner.Name -notmatch '^pythonw?\.exe$' -or $owner.CommandLine -notmatch 'asterion_remote\.native_phone_relay:app'){
    throw 'Port 8995 owned by unrecognized process; refusing restart'
  }
  $task=Get-ScheduledTask -TaskName 'Asterion Control Self-Healing Worker' -ErrorAction Stop
  if($task.State -eq 'Disabled'){throw 'Original watchdog disabled'}
  $token=(Get-Content -LiteralPath (Join-Path $state 'control-token.txt') -Raw).Trim()
  $url=(Get-Content -LiteralPath (Join-Path $state 'agent-host.txt') -Raw).Trim()
  if($token.Length -lt 32 -or $url -notmatch '^http://[0-9.]+:8911$'){throw 'Original worker authorization unavailable'}
  # The caller has returned its native job receipt before this detached runner.
  $jobs=Invoke-RestMethod ($url+'/api/v1/commands') -Headers @{Authorization=('Bearer '+$token)} -TimeoutSec 5
  if(@($jobs.items|Where-Object{$_.status -eq 'running'}).Count -gt 0){
    Save-Receipt 'deferred_busy' $false 'Native Windows jobs still active' @{}
    exit 2
  }
  if(-not $Apply){
    Save-Receipt 'ready' $true 'Read-only preflight passed; relay unchanged' @{old_pid=$pidBefore;rpc_http=$route}
    exit 0
  }
  Save-Receipt 'reloading' $false 'Original WSS relay restart requested' @{old_pid=$pidBefore;old_rpc_http=$route}
  Stop-Process -Id $pidBefore -ErrorAction Stop
  $free=$false
  for($i=0;$i -lt 30;$i++){
    Start-Sleep -Milliseconds 200
    if(@(Get-NetTCPConnection -LocalPort 8995 -State Listen -ErrorAction SilentlyContinue).Count -eq 0){$free=$true;break}
  }
  if(-not $free){throw 'Original WSS listener did not close; not starting duplicate'}
  $py=Join-Path $root '.venv\Scripts\python.exe'
  $child=Start-Process -FilePath $py -ArgumentList @('-m','uvicorn','asterion_remote.native_phone_relay:app','--host','127.0.0.1','--port','8995') -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $state 'native-wss.stdout.log') -RedirectStandardError (Join-Path $state 'native-wss.stderr.log')
  $healthy=$false;$routeReady=$false;$connected=$false
  for($i=0;$i -lt 60;$i++){
    Start-Sleep -Milliseconds 500
    $now=Native-Health
    if($now){$healthy=$true;$connected=[bool]$now.phone_connected}
    if((Rpc-Status) -eq 405){$routeReady=$true}
    if($healthy -and $routeReady -and $connected){break}
  }
  $verified=$false;$network='unknown'
  if($healthy -and $routeReady -and $connected){
    $pairPath=Join-Path $state 'phone-pairing.json'
    if(Test-Path -LiteralPath $pairPath){
      $pair=Get-Content -LiteralPath $pairPath -Raw|ConvertFrom-Json
      $body=@{path='/network/status';method='GET';timeout_seconds=5}|ConvertTo-Json -Compress
      try{
        $r=Invoke-RestMethod 'http://127.0.0.1:8995/phone/rpc' -Method Post -Headers @{Authorization=('Bearer '+[string]$pair.token)} -ContentType 'application/json' -Body $body -TimeoutSec 8
        $verified=($r.transport -eq 'native_wss' -and $r.kind -eq 'json' -and $r.value.network -in @('wifi','cellular','ethernet','none'))
        if($verified){$network=[string]$r.value.network}
      }catch{}
    }
  }
  Save-Receipt $(if($verified){'verified'}else{'incomplete'}) $verified $(if($verified){'Authenticated phone RPC round-trip succeeded'}else{'Native WSS source or Android reconnect unverified'}) @{old_pid=$pidBefore;new_pid=$child.Id;relay_healthy=$healthy;rpc_route_present=$routeReady;phone_reconnected=$connected;roundtrip_verified=$verified;phone_network=$network;cellular_verified=($verified -and $network -eq 'cellular')}
  if(-not $verified){exit 3}
}catch{
  Save-Receipt 'blocked' $false $_.Exception.GetType().Name @{owner_pairing_preserved=$true}
  exit 1
}
