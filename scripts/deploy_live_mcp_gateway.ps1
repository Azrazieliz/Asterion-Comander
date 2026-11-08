# Rollback-safe update of existing ChatGPT/OAuth MCP gateway (port 8996).
# Preserve all owner keys, OAuth state, Android APK and private agent services.
$ErrorActionPreference='Stop'
$dev='D:\AsterionControlV092Build'
$release='D:\AsterionControlRelease'
$py=Join-Path $release '.venv\Scripts\python.exe'
$target=Join-Path $release 'asterion_remote\mcp_gateway.py'
$new=Join-Path $dev 'asterion_remote\mcp_gateway.py'
$bridgeNew=Join-Path $dev 'asterion_remote\live_operator_bridge.py'
$bridgeTarget=Join-Path $release 'asterion_remote\live_operator_bridge.py'
$verify=Join-Path $dev 'scripts\verify_live_mcp_http.py'
$address='127.0.0.1'
$port=8996
$stamp=Get-Date -Format 'yyyyMMdd_HHmmss'
$backupDir=Join-Path $release '_control_live_backups'
$gatewayBackup=Join-Path $backupDir ('mcp_gateway_before_live_'+$stamp+'.py')
$bridgeBackup=Join-Path $backupDir ('live_operator_bridge_before_live_'+$stamp+'.py')
$hadBridge=Test-Path $bridgeTarget
$installed=$false

function Hash([string]$file){return (Get-FileHash -Algorithm SHA256 -LiteralPath $file).Hash.ToUpperInvariant()}
function Listener(){@((Get-NetTCPConnection -LocalAddress $address -LocalPort $port -State Listen -ErrorAction SilentlyContinue))}
function WaitListener([bool]$want,[int]$seconds=16){
  $until=(Get-Date).AddSeconds($seconds)
  do {
    if((@((Listener)).Count -gt 0) -eq $want){return $true}
    Start-Sleep -Milliseconds 160
  }while((Get-Date) -lt $until)
  return $false
}
function StopGateway(){
  foreach($item in @(Listener)){
    $proc=Get-CimInstance Win32_Process -Filter ('ProcessId='+$item.OwningProcess) -ErrorAction SilentlyContinue
    if($proc -and $proc.CommandLine -match 'uvicorn asterion_remote.mcp_gateway:app'){
      Stop-Process -Id $item.OwningProcess -Force -ErrorAction SilentlyContinue
    }else{
      throw 'Refusing to stop unrelated process on MCP gateway port'
    }
  }
  if(-not (WaitListener $false 8)){throw 'Previous MCP gateway did not close'}
}
function StartGateway(){
  $logdir=Join-Path $release '_control_live_logs'
  New-Item -Path $logdir -ItemType Directory -Force | Out-Null
  $out=Join-Path $logdir ('mcp_'+$stamp+'.stdout.log')
  $err=Join-Path $logdir ('mcp_'+$stamp+'.stderr.log')
  $args=@('-m','uvicorn','asterion_remote.mcp_gateway:app','--host',$address,'--port',"$port")
  $proc=Start-Process -FilePath $py -ArgumentList $args -WorkingDirectory $release -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
  if(-not (WaitListener $true 16)){throw 'MCP gateway did not bind local port'}
  return $proc.Id
}
if(-not (Test-Path $new) -or -not (Test-Path $bridgeNew)){throw 'New MCP gateway source is missing'}
$oldHash=Hash $target
$newHash=Hash $new
$listener=@(Listener)
if($listener.Count -ne 1){throw 'Expected one active private MCP gateway'}
$oldPid=[int]$listener[0].OwningProcess
$oldProc=Get-CimInstance Win32_Process -Filter ('ProcessId='+$oldPid)
if(-not $oldProc -or $oldProc.CommandLine -notmatch 'uvicorn asterion_remote.mcp_gateway:app'){
  throw 'Unexpected MCP gateway listener owner'
}
New-Item -Path $backupDir -ItemType Directory -Force | Out-Null
Copy-Item -LiteralPath $target -Destination $gatewayBackup -Force
if($hadBridge){Copy-Item -LiteralPath $bridgeTarget -Destination $bridgeBackup -Force}
if((Hash $gatewayBackup) -ne $oldHash){throw 'MCP backup integrity check failed'}
try {
  Copy-Item -LiteralPath $new -Destination $target -Force
  Copy-Item -LiteralPath $bridgeNew -Destination $bridgeTarget -Force
  $installed=$true
  if((Hash $target) -ne $newHash){throw 'New MCP gateway source checksum mismatch'}
  & $py -m py_compile $target $bridgeTarget
  if($LASTEXITCODE -ne 0){throw 'New gateway Python syntax failed'}
  StopGateway
  $newPid=StartGateway
  & $py $verify
  if($LASTEXITCODE -ne 0){throw 'Production ChatGPT MCP tool acceptance failed'}
  Write-Output ('CONTROL_MCP_DEPLOYED '+(ConvertTo-Json -Compress @{
    status='verified';old_pid=$oldPid;new_pid=$newPid;
    installed_hash=$newHash;backup=$gatewayBackup;
    authenticated_mcp_live_tools=$true;phone_action_not_executed=$true
  }))
}catch{
  $msg=$_.Exception.Message
  Write-Output ('CONTROL_MCP_DEPLOY_ERROR '+$msg)
  try{
    if($installed){
      StopGateway
      Copy-Item -LiteralPath $gatewayBackup -Destination $target -Force
      if($hadBridge){Copy-Item -LiteralPath $bridgeBackup -Destination $bridgeTarget -Force}
      else{Remove-Item -LiteralPath $bridgeTarget -Force -ErrorAction SilentlyContinue}
      if((Hash $target) -ne $oldHash){throw 'Rollback source checksum mismatch'}
      $pidRestored=StartGateway
      Write-Output ('CONTROL_MCP_ROLLBACK_RESTORED pid='+$pidRestored)
    }
  }catch{Write-Output ('CONTROL_MCP_ROLLBACK_ERROR '+$_.Exception.Message)}
  throw 'Interactive MCP deployment failed; rollback attempted'
}
