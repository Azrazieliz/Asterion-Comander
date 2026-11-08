# Rollback-safe upgrade of the established Windows Asterion Control LAN server.
# Changes the live_stream module only; existing owner keys and all other services persist.
param([switch]$DryRun)
$ErrorActionPreference='Stop'
$sourceRoot='D:\AsterionControlV092Build'
$releaseRoot='D:\AsterionControlRelease'
$source=Join-Path $sourceRoot 'asterion_remote\live_stream.py'
$destination=Join-Path $releaseRoot 'asterion_remote\live_stream.py'
$operatorSource=Join-Path $sourceRoot 'scripts\live_phone_operator.py'
$operatorDest=Join-Path $releaseRoot 'scripts\live_phone_operator.py'
$docSource=Join-Path $sourceRoot 'docs\DEFAULT_LIVE_ACTION_INTERFACE.md'
$docDest=Join-Path $releaseRoot 'docs\DEFAULT_LIVE_ACTION_INTERFACE.md'
$python=Join-Path $releaseRoot '.venv\Scripts\python.exe'
$verify=Join-Path $sourceRoot 'scripts\verify_live_control_deployed.py'
$oldExpected='56B22161122AEF48FE6D543B4835558C0264CA32FD862AE1B90F466F44EA6BB5'
$newExpected='1E71633AD8A2E6914298214FA291ACAF3B0F5CA6105AB307D9330ED5FC6B692C'
$address='192.168.1.133'
$port=8911
$stamp=Get-Date -Format 'yyyyMMdd_HHmmss'
$backupDir=Join-Path $releaseRoot '_control_live_backups'
$backup=Join-Path $backupDir ('live_stream_before_state_guard_'+$stamp+'.py')
$installed=$false

function SourceHash([string]$path){return (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToUpperInvariant()}
function Listener(){@((Get-NetTCPConnection -LocalAddress $address -LocalPort $port -State Listen -ErrorAction SilentlyContinue))}
function WaitListener([bool]$want,[int]$seconds=16){
  $until=(Get-Date).AddSeconds($seconds)
  do {
    if((@((Listener)).Count -gt 0) -eq $want){return $true}
    Start-Sleep -Milliseconds 160
  } while((Get-Date) -lt $until)
  return $false
}
function StopListener(){
  foreach($item in @(Listener)){
    $p=Get-CimInstance Win32_Process -Filter ('ProcessId='+$item.OwningProcess) -ErrorAction SilentlyContinue
    if($p -and $p.CommandLine -match 'uvicorn asterion_remote.app:app'){
      Stop-Process -Id $item.OwningProcess -Force -ErrorAction SilentlyContinue
    } else {
      throw 'Refusing to stop an unrelated process on the Control port'
    }
  }
  if(-not (WaitListener $false 8)){throw 'Previous Control server did not release port'}
}
function StartControl(){
  $logs=Join-Path $releaseRoot '_control_live_logs'
  New-Item -Path $logs -ItemType Directory -Force | Out-Null
  $stdout=Join-Path $logs ('control_'+$stamp+'.stdout.log')
  $stderr=Join-Path $logs ('control_'+$stamp+'.stderr.log')
  $args=@('-m','uvicorn','asterion_remote.app:app','--host',$address,'--port',"$port")
  $p=Start-Process -FilePath $python -ArgumentList $args -WorkingDirectory $releaseRoot -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
  if(-not (WaitListener $true 16)){throw 'Updated Control server failed to open the previous address'}
  return $p.Id
}
if(-not (Test-Path $source) -or -not (Test-Path $python)){throw 'Control source/runtime missing'}
$oldHash=SourceHash $destination
$newHash=SourceHash $source
if($oldHash -ne $oldExpected){throw 'Production source changed: refusing unreviewed overwrite'}
if($newHash -ne $newExpected){throw 'Development source changed: refusing unreviewed overwrite'}
$existing=@(Listener)
if($existing.Count -ne 1){throw 'Expected exactly one canonical private Control listener'}
$oldPid=[int]$existing[0].OwningProcess
$oldProc=Get-CimInstance Win32_Process -Filter ('ProcessId='+$oldPid)
if(-not $oldProc -or $oldProc.CommandLine -notmatch 'uvicorn asterion_remote.app:app'){throw 'Control listener ownership mismatch'}
if($DryRun){
  Write-Output ('CONTROL_DEPLOY_DRY_RUN '+(ConvertTo-Json -Compress @{status='verified';old_pid=$oldPid;old_hash=$oldHash;new_hash=$newHash}))
  exit 0
}
New-Item -Path $backupDir -ItemType Directory -Force | Out-Null
Copy-Item -LiteralPath $destination -Destination $backup -Force
if((SourceHash $backup) -ne $oldHash){throw 'Could not verify rollback copy'}
try {
  Copy-Item -LiteralPath $source -Destination $destination -Force
  $installed=$true
  if((SourceHash $destination) -ne $newHash){throw 'Updated source integrity mismatch'}
  & $python -m py_compile $destination
  if($LASTEXITCODE -ne 0){throw 'Python compilation failed'}
  StopListener
  $newPid=StartControl
  & $python $verify
  if($LASTEXITCODE -ne 0){throw 'State-aware production acceptance failed'}
  New-Item -Path (Split-Path $operatorDest -Parent) -ItemType Directory -Force | Out-Null
  New-Item -Path (Split-Path $docDest -Parent) -ItemType Directory -Force | Out-Null
  Copy-Item -LiteralPath $operatorSource -Destination $operatorDest -Force
  Copy-Item -LiteralPath $docSource -Destination $docDest -Force
  Write-Output ('CONTROL_DEPLOY_RESULT '+(ConvertTo-Json -Compress @{
    status='verified';previous_pid=$oldPid;current_pid=$newPid;
    source_hash=$newHash;backup=$backup;operator_installed=$true;
    phone_inspect_verified=$true;stale_action_rejected=$true
  }))
} catch {
  Write-Output ('CONTROL_DEPLOY_ERROR '+$_.Exception.Message)
  try {
    if($installed){
      StopListener
      Copy-Item -LiteralPath $backup -Destination $destination -Force
      if((SourceHash $destination) -ne $oldHash){throw 'Rollback file hash mismatch'}
      $restoredPid=StartControl
      Write-Output ('CONTROL_ROLLBACK_RESTORED pid='+$restoredPid)
    }
  } catch {Write-Output ('CONTROL_ROLLBACK_FAILURE '+$_.Exception.Message)}
  throw 'Control live state-aware deployment did not pass acceptance'
}
