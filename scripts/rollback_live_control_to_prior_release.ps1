# Restore the exact verified pre-change Windows Asterion Control modules.
# Uses the original deployment backups; does not touch Android, credentials,
# other Windows processes or the requested shared bridge default policy.
$ErrorActionPreference='Stop'
$root='D:\AsterionControlRelease'
$python=Join-Path $root '.venv\Scripts\python.exe'
$directory=Join-Path $root 'asterion_remote'
$backupDir=Join-Path $root '_control_live_backups'
$restore=@(
  @{file='mcp_gateway.py';old='FA7715D8DB4D45EFEC3B33C50E1B8B5DD469DD0F4912BC7B0BA53F8A45056DFB';backup='mcp_gateway_before_live_20261108_124810.py';new='674A1198E1B8542D8FD61017835C253DBD55072734EDDAD8717A2AF0DF2401E8'},
  @{file='live_stream.py';old='56B22161122AEF48FE6D543B4835558C0264CA32FD862AE1B90F466F44EA6BB5';backup='live_stream_before_state_guard_20261108_124144.py';new='1E71633AD8A2E6914298214FA291ACAF3B0F5CA6105AB307D9330ED5FC6B692C'}
)
function Hash([string]$path) {
  return (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToUpperInvariant()
}
foreach($item in $restore) {
  $dest=Join-Path $directory $item.file
  $backup=Join-Path $backupDir $item.backup
  if(!(Test-Path $backup)){throw ('Missing exact pre-change backup '+$item.file)}
  if((Hash $backup) -ne $item.old){throw ('Pre-change backup failed hash check '+$item.file)}
  if((Hash $dest) -notin @($item.old,$item.new)){
    throw ('Current '+$item.file+' was modified by something else; refuse overwrite')
  }
}
function Port([string]$address,[int]$port) {
  return @(Get-NetTCPConnection -LocalAddress $address -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}
function WaitPort([string]$address,[int]$port,[bool]$present) {
  $until=(Get-Date).AddSeconds(16)
  do{
    $observed=@(Get-NetTCPConnection -LocalAddress $address -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
    if(($observed.Count -gt 0) -eq $present){return $true}
    Start-Sleep -Milliseconds 160
  }while((Get-Date) -lt $until)
  return $false
}
function RestartCanonical([string]$module,[string]$address,[int]$port) {
  $listeners=@(Port $address $port)
  if($listeners.Count -ne 1){throw ('Unexpected listener count on '+$port+': '+$listeners.Count)}
  $ownerId=[int]$listeners[0].OwningProcess
  $process=Get-CimInstance Win32_Process -Filter ('ProcessId='+$ownerId)
  if(!$process -or $process.CommandLine -notmatch [regex]::Escape('uvicorn '+$module+':app')){
    throw ('Refusing to terminate unrelated process on '+$port)
  }
  Stop-Process -Id $ownerId -Force
  if(-not (WaitPort $address $port $false)){throw ('Old listener still active '+$port)}
  $logDir=Join-Path $root '_control_live_logs'
  New-Item -ItemType Directory -Path $logDir -Force | Out-Null
  $prefix='rollback_'+$port+'_'+(Get-Date -Format 'yyyyMMdd_HHmmss')
  $output=Join-Path $logDir ($prefix+'.stdout.log')
  $errors=Join-Path $logDir ($prefix+'.stderr.log')
  $arguments=@('-m','uvicorn',($module+':app'),'--host',$address,'--port',"$port")
  $newProc=Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput $output -RedirectStandardError $errors -PassThru
  if(-not (WaitPort $address $port $true)){throw ('Restored listener did not start '+$port)}
  Write-Output ('RESTORED_SERVICE port='+$port+' previous_pid='+$ownerId+' new_pid='+$newProc.Id)
}
# Restore exact originals first. Running services keep their old imports until restarted.
foreach($item in $restore) {
  $dest=Join-Path $directory $item.file
  $backup=Join-Path $backupDir $item.backup
  Copy-Item -LiteralPath $backup -Destination $dest -Force
  if((Hash $dest) -ne $item.old){throw ('Failed to restore '+$item.file)}
}
# Restore gateway and native-stream server independently.
# The gateway already restarted with original source in the prior attempt.
# Do not interrupt it twice: the only remaining old process is port 8911.
$gateway=@(Get-NetTCPConnection -LocalAddress '127.0.0.1' -LocalPort 8996 -State Listen -ErrorAction SilentlyContinue)
if($gateway.Count -ne 1){throw 'Previously restored MCP gateway not listening'}
RestartCanonical 'asterion_remote.app' '192.168.1.133' 8911
# Remove only new objects that did not exist before our unrequested changes.
$created=@(
 (Join-Path $directory 'live_operator_bridge.py'),
 (Join-Path $root 'scripts\live_phone_operator.py'),
 (Join-Path $root 'docs\DEFAULT_LIVE_ACTION_INTERFACE.md')
)
foreach($p in $created){if(Test-Path $p){Remove-Item -LiteralPath $p -Force}}
foreach($item in $restore){
  $dest=Join-Path $directory $item.file
  if((Hash $dest) -ne $item.old){throw ('Post-restart source checksum mismatch '+$item.file)}
}
Write-Output ('ROLLBACK_COMPLETE '+(ConvertTo-Json -Compress @{
  status='restored';release='pre_state_aware_Windows_Control';
  mcp_gateway_sha256=(Hash (Join-Path $directory 'mcp_gateway.py'));
  live_stream_sha256=(Hash (Join-Path $directory 'live_stream.py'));
  listener_mcp=@(Get-NetTCPConnection -LocalAddress '127.0.0.1' -LocalPort 8996 -State Listen -ErrorAction SilentlyContinue).Count;
  listener_lan=@(Get-NetTCPConnection -LocalAddress '192.168.1.133' -LocalPort 8911 -State Listen -ErrorAction SilentlyContinue).Count;
  apk_unchanged=$true;credentials_unchanged=$true
}))
