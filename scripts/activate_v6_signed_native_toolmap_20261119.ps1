# Reload ONLY the original owner-paired native WSS process after reviewed M3/M4 toolmap.
# Detached maintenance; does not touch pairing, Android data, keys or other engines.
param([switch]$Apply)
$ErrorActionPreference='Stop'
if($Apply){Start-Sleep -Seconds 12}
$root='D:\AsterionControlRelease'
$state=Join-Path $env:LOCALAPPDATA 'AsterionControl'
$report=Join-Path $state 'v6-signed-native-m3m4-activation.json'
function Save-Receipt([string]$phase,[bool]$verified,[hashtable]$details){
  $info=[ordered]@{phase=$phase;verified=$verified;observed_at=(Get-Date -Format o);owner_pairing_preserved=$true;original_gateway_only=$true}
  foreach($k in $details.Keys){$info[$k]=$details[$k]}
  $tmp=$report+'.partial'
  [IO.File]::WriteAllText($tmp,($info|ConvertTo-Json -Depth 5 -Compress),(New-Object System.Text.UTF8Encoding($false)))
  Move-Item -LiteralPath $tmp -Destination $report -Force
}
function Owner-Relay {
  $sockets=@(Get-NetTCPConnection -LocalPort 8995 -State Listen -ErrorAction SilentlyContinue)
  if($sockets.Count -ne 1){throw 'Native relay listener count unexpected'}
  $proc=Get-CimInstance Win32_Process -Filter ('ProcessId='+[int]$sockets[0].OwningProcess)
  if(-not $proc -or $proc.Name -notmatch '^pythonw?\.exe$' -or $proc.CommandLine -notmatch 'asterion_remote\.native_phone_relay:app'){
    throw 'WSS listener is not owned by original Control relay'
  }
  return $proc
}
function Worker-Idle {
  $base=(Get-Content (Join-Path $state 'agent-host.txt') -Raw).Trim()
  $secret=(Get-Content (Join-Path $state 'control-token.txt') -Raw).Trim()
  if($secret.Length -lt 32 -or $base -notmatch '^http://[0-9.]+:8911$'){throw 'Original Windows API authorization missing'}
  $jobs=Invoke-RestMethod ($base+'/api/v1/commands') -Headers @{Authorization=('Bearer '+$secret)} -TimeoutSec 5
  return (@($jobs.items|Where-Object{$_.status -eq 'running'}).Count -eq 0)
}
function Android-WSS-Roundtrip {
  try{
    $pair=Get-Content (Join-Path $state 'phone-pairing.json') -Raw|ConvertFrom-Json
    $data=@{path='/network/status';method='GET';timeout_seconds=5}|ConvertTo-Json -Compress
    $r=Invoke-RestMethod 'http://127.0.0.1:8995/phone/rpc' -Method Post -Headers @{Authorization=('Bearer '+[string]$pair.token)} -ContentType 'application/json' -Body $data -TimeoutSec 8
    return ($r.transport -eq 'native_wss' -and $r.kind -eq 'json' -and $r.value.network -in @('wifi','cellular','vpn','ethernet'))
  }catch{return $false}
}
try{
  $file=Join-Path $root 'asterion_remote\native_phone_rpc.py'
  $py=Join-Path $root '.venv\Scripts\python.exe'
  if(-not(Test-Path $file) -or -not(Test-Path $py)){throw 'Original WSS runtime absent'}
  $hash=(Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
  if($hash -ne '2bfb221123874cd95f086472fef73baadd1bbcdb19a4d5e2f22c2f26fe706f94'){
    throw 'Original WSS toolmap checksum differs from reviewed deployed source'
  }
  if(-not(Worker-Idle)){
    Save-Receipt 'deferred_busy' $false @{reason='Original Windows jobs are running'}
    exit 2
  }
  $before=Owner-Relay
  if(-not(Android-WSS-Roundtrip)){throw 'Original Android WSS not healthy before refresh'}
  if(-not $Apply){
    Save-Receipt 'dry_run_success' $true @{old_pid=[int]$before.ProcessId;toolmap_sha256=$hash}
    exit 0
  }
  Save-Receipt 'reloading' $false @{old_pid=[int]$before.ProcessId;toolmap_sha256=$hash}
  Stop-Process -Id $before.ProcessId -ErrorAction Stop
  $free=$false
  for($i=0;$i -lt 30;$i++){
    Start-Sleep -Milliseconds 200
    if(@(Get-NetTCPConnection -LocalPort 8995 -State Listen -ErrorAction SilentlyContinue).Count -eq 0){$free=$true;break}
  }
  if(-not $free){throw 'Original WSS port still occupied; refusing duplicate'}
  $child=Start-Process -FilePath $py -ArgumentList @('-m','uvicorn','asterion_remote.native_phone_relay:app','--host','127.0.0.1','--port','8995') -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $state 'native-wss.stdout.log') -RedirectStandardError (Join-Path $state 'native-wss.stderr.log')
  $ok=$false
  for($i=0;$i -lt 70;$i++){
    Start-Sleep -Milliseconds 600
    if(Android-WSS-Roundtrip){$ok=$true;break}
  }
  Save-Receipt $(if($ok){'verified'}else{'incomplete'}) $ok @{old_pid=[int]$before.ProcessId;new_pid=[int]$child.Id;native_toolmap_sha256=$hash;android_authenticated_roundtrip=$ok}
  if(-not $ok){exit 3}
}catch{
  Save-Receipt 'blocked_or_failed' $false @{error_class=$_.Exception.GetType().Name}
  exit 1
}
