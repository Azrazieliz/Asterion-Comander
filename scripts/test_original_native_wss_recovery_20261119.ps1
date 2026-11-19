# Real P-1 fault injection. Original paired native WSS relay only.
# No new gateway, ADB, credentials, Android changes, re-pairing or second engine.
param([ValidateRange(1,3)][int]$Trials=2,[switch]$Apply)
$ErrorActionPreference='Stop'
$root='D:\AsterionControlRelease'
$state=Join-Path $env:LOCALAPPDATA 'AsterionControl'
$report=Join-Path $state 'v6-native-wss-fault-trials.json'
$taskName='Asterion Control Self-Healing Worker'
$record=New-Object System.Collections.ArrayList
function Write-Report([string]$phase,[bool]$passed){
  $out=[ordered]@{phase=$phase;passed=$passed;trials=$record.ToArray();
      at=(Get-Date -Format o);owner_pairing_mutated=$false}
  $tmp=$report+'.new'
  [IO.File]::WriteAllText($tmp,($out|ConvertTo-Json -Depth 6 -Compress),(New-Object System.Text.UTF8Encoding($false)))
  Move-Item -LiteralPath $tmp -Destination $report -Force
}
function Live-Process{
  $listeners=@(Get-NetTCPConnection -LocalPort 8995 -State Listen -ErrorAction SilentlyContinue)
  if($listeners.Count -ne 1){throw 'Native WSS port not uniquely owned'}
  $process=Get-CimInstance Win32_Process -Filter ('ProcessId='+$listeners[0].OwningProcess) -ErrorAction Stop
  if(-not $process -or $process.Name -notmatch '^pythonw?\.exe$' -or
       $process.CommandLine -notmatch 'asterion_remote\.native_phone_relay:app'){
    throw 'Port 8995 is not original owner WSS relay'
  }
  return $process
}
function Windows-Idle{
  $base=(Get-Content (Join-Path $state 'agent-host.txt') -Raw).Trim()
  $key=(Get-Content (Join-Path $state 'control-token.txt') -Raw).Trim()
  if($key.Length -lt 32){throw 'Original authorization missing'}
  $jobs=Invoke-RestMethod ($base+'/api/v1/commands') -Headers @{Authorization=('Bearer '+$key)} -TimeoutSec 5
  return (@($jobs.items|Where-Object{$_.status -eq 'running'}).Count -eq 0)
}
function Native-Probe{
  try{
    $healthy=Invoke-RestMethod 'http://127.0.0.1:8995/healthz' -TimeoutSec 2
    if(-not $healthy.ok -or -not $healthy.phone_connected){return $null}
    $pair=Get-Content (Join-Path $state 'phone-pairing.json') -Raw|ConvertFrom-Json
    $body=@{path='/network/status';method='GET';timeout_seconds=5}|ConvertTo-Json -Compress
    $r=Invoke-RestMethod 'http://127.0.0.1:8995/phone/rpc' -Method Post -Headers @{Authorization=('Bearer '+[string]$pair.token)} -ContentType 'application/json' -Body $body -TimeoutSec 8
    if($r.transport -eq 'native_wss' -and $r.kind -eq 'json' -and $r.value.network -in @('wifi','cellular','ethernet','vpn')){
      return [string]$r.value.network
    }
  }catch{}
  return $null
}
function Restore-Existing{
  $listeners=@(Get-NetTCPConnection -LocalPort 8995 -State Listen -ErrorAction SilentlyContinue)
  if($listeners.Count -gt 0){return}
  $py=Join-Path $root '.venv\Scripts\python.exe'
  if(-not(Test-Path -LiteralPath $py)){return}
  Start-Process -FilePath $py -ArgumentList @('-m','uvicorn','asterion_remote.native_phone_relay:app','--host','127.0.0.1','--port','8995') -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $state 'native-wss.stdout.log') -RedirectStandardError (Join-Path $state 'native-wss.stderr.log')|Out-Null
}
try{
  if(-not(Test-Path -LiteralPath $root)){throw 'Owner Control release not installed'}
  $task=Get-ScheduledTask -TaskName $taskName -ErrorAction Stop
  if($task.State -eq 'Disabled'){throw 'Original watchdog disabled'}
  if(-not(Windows-Idle)){throw 'Another Windows Control command is running'}
  $existing=Live-Process
  $network=Native-Probe
  if(-not $network){throw 'Existing authenticated WSS roundtrip unavailable'}
  if(-not $Apply){
    [void]$record.Add(@{preflight=true;original_pid=$existing.ProcessId;network=$network;relay_mutated=$false})
    Write-Report 'dry_run' $true
    exit 0
  }
  for($i=1;$i -le $Trials;$i++){
    if(-not(Windows-Idle)){throw 'Native Windows job appeared; recovery test deferred'}
    $original=Live-Process
    if(-not(Native-Probe)){throw 'Native Android RPC failed before trial'}
    $sw=[Diagnostics.Stopwatch]::StartNew()
    Stop-Process -Id $original.ProcessId -ErrorAction Stop
    Start-Sleep -Milliseconds 600
    $stopped=(@(Get-NetTCPConnection -LocalPort 8995 -State Listen -ErrorAction SilentlyContinue).Count -eq 0)
    if($stopped){Start-ScheduledTask -TaskName $taskName -ErrorAction Stop}
    $verified=$false;$newPid=0;$mode=''
    for($n=0;$n -lt 65;$n++){
      Start-Sleep -Seconds 1
      try{
        $now=Live-Process
        if([int]$now.ProcessId -eq [int]$original.ProcessId){continue}
        $mode=Native-Probe
        if($mode){$verified=$true;$newPid=[int]$now.ProcessId;break}
      }catch{}
    }
    $sw.Stop()
    [void]$record.Add(@{trial=$i;original_pid=[int]$original.ProcessId;new_pid=$newPid;
      process_stopped=$stopped;original_watchdog_verified=$verified;
      authenticated_android_rpc=$verified;network=$mode;recovery_ms=$sw.ElapsedMilliseconds})
    Write-Report 'in_progress' $false
    if(-not $verified){throw 'Original watchdog recovery was not verified'}
    Start-Sleep -Seconds 3
  }
  Write-Report 'verified' $true
}catch{
  try{Restore-Existing}catch{}
  [void]$record.Add(@{failure_class=$_.Exception.GetType().Name;verified=$false})
  Write-Report 'failed_or_blocked' $false
  exit 2
}
