# One-time migration: retire the callable MCP/OAuth gateway but preserve the
# phone's EXISTING stable native /phone/live WSS tunnel and Android pairing.
# Owner-approved. Never reset credentials, SSH identity or installed Android app.
$ErrorActionPreference='Stop'
$root='D:\AsterionControlRelease'
$state=Join-Path $env:LOCALAPPDATA 'AsterionControl'
$python=Join-Path $root '.venv\Scripts\python.exe'
$relay=Join-Path $root 'asterion_remote\native_phone_relay.py'
$start=Join-Path $root 'scripts\start_native_wss_tunnel.py'
if(-not(Test-Path $relay) -or -not(Test-Path $start) -or -not(Test-Path $python)){
  throw 'Reviewed native relay not installed; refusing old gateway shutdown'
}
if(-not(Test-Path (Join-Path $state 'mcp-stable-ssh-ed25519')) -or
   -not(Test-Path (Join-Path $state 'mcp-stable-known-hosts'))){
  throw 'Existing pinned SSH identity missing; do not rotate or cut over'
}
function Native-Health {
  try{
    $result=Invoke-RestMethod 'http://127.0.0.1:8995/healthz' -TimeoutSec 3
    return [bool]($result.ok -and $result.service -eq 'asterion-native-phone-wss')
  }catch{return $false}
}
# Shut down ONLY processes positively identified as the obsolete gateway.
foreach($port in @(8995,8996)){
  $list=@(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
  foreach($listener in $list){
    $owner=Get-CimInstance Win32_Process -Filter ('ProcessId='+$listener.OwningProcess) -ErrorAction SilentlyContinue
    if(-not $owner){throw ('Unknown listener on port '+$port)}
    if($owner.CommandLine -match 'asterion_remote\.native_phone_relay:app'){continue}
    if($owner.Name -match '^pythonw?\.exe$' -and
       ($owner.CommandLine -match 'asterion_remote\.mcp_gateway:app' -or
        $owner.CommandLine -match 'run_gateway_096\.py')){
      Stop-Process -Id $owner.ProcessId -Force -ErrorAction Stop
    }else{
      throw ('Unexpected listener on port '+$port+'; refusing interruption')
    }
  }
}
if(-not(Native-Health)){
  for($i=0;$i -lt 10;$i++){
    if(@(Get-NetTCPConnection -State Listen -LocalPort 8995 -ErrorAction SilentlyContinue).Count -eq 0){break}
    Start-Sleep -Milliseconds 200
  }
  if(@(Get-NetTCPConnection -State Listen -LocalPort 8995 -ErrorAction SilentlyContinue).Count -gt 0){
    throw 'Unknown listener remains on native WSS port 8995'
  }
  Start-Process -FilePath $python -ArgumentList @('-m','uvicorn',
    'asterion_remote.native_phone_relay:app','--host','127.0.0.1','--port','8995') `
    -WorkingDirectory $root -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $state 'native-wss.stdout.log') `
    -RedirectStandardError (Join-Path $state 'native-wss.stderr.log')|Out-Null
}
$healthy=$false
for($n=0;$n -lt 25;$n++){
  if(Native-Health){$healthy=$true;break}
  Start-Sleep -Milliseconds 250
}
if(-not $healthy){throw 'Native relay did not become healthy; consult native-wss stderr'}
# The old stable SSH supervisor manages the same public WSS route but tries
# to validate /mcp. Gracefully release its flag before the new supervisor.
$oldFlag=Join-Path $state 'mcp-stable-ssh-enabled.flag'
if(Test-Path $oldFlag){Remove-Item $oldFlag -Force}
$flag=Join-Path $state 'native-wss-enabled.flag'
if(-not(Test-Path $flag)){[IO.File]::WriteAllText($flag,'enabled')}
# Retire obsolete gateway entry-point files from active Python/module paths.
# Preserve source backups outside the running service tree for audit/rollback.
$archive=Join-Path $state ('backups\retired-gateway-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $archive -Force|Out-Null
$obsolete=@(
  'asterion_remote\mcp_gateway.py','asterion_remote\mcp_protocol.py',
  'asterion_remote\mcp_setup.py','asterion_remote\oauth_bridge.py',
  'asterion_remote\phone_live.py',
  'scripts\run_gateway_096.py','scripts\start_mcp_gateway.ps1',
  'scripts\start_persistent_mcp_funnel.ps1',
  'scripts\start_persistent_ssh_mcp.py',
  'scripts\deploy_mcp_oauth_20261106.ps1',
  'scripts\deploy_mcp_oauth_safe_20261106.ps1',
  'scripts\deploy_mcp_oauth_safe_20261106_v2.ps1',
  'scripts\probe_mcp_public.py','scripts\verify_active_mcp.py'
)
foreach($part in $obsolete){
  $old=Join-Path $root $part
  if(Test-Path $old){
    Move-Item $old (Join-Path $archive (($part -replace '[\\/]','_')+'.retired')) -Force
  }
}
# A matching existing SSH forward can now gracefully exit and reconnect under
# the new native supervisor. An exact old SSH process may take up to ~10 sec
# to finish; the phone's WSS automatically reconnects.
$oldSupervisor=@(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
  Where-Object{$_.CommandLine -match 'start_persistent_ssh_mcp\.py'})
foreach($p in $oldSupervisor){try{Stop-Process -Id $p.ProcessId -Force}catch{}}
$oldSsh=@(Get-CimInstance Win32_Process -Filter "Name = 'ssh.exe'" -ErrorAction SilentlyContinue |
  Where-Object{$_.CommandLine -match '80:127\.0\.0\.1:8995' -and
    $_.CommandLine -match 'stable@proxy\.tunnl\.gg'})
foreach($p in $oldSsh){try{Stop-Process -Id $p.ProcessId -Force}catch{}}
$supervisor=@(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
  Where-Object{$_.CommandLine -match 'start_native_wss_tunnel\.py'})
if($supervisor.Count -eq 0){
  Start-Process -FilePath $python -ArgumentList @($start) -WorkingDirectory $root `
    -WindowStyle Hidden -RedirectStandardOutput (Join-Path $state 'native-wss-tunnel.stdout.log') `
    -RedirectStandardError (Join-Path $state 'native-wss-tunnel.stderr.log')|Out-Null
}
# The old Cloudflare trial is not needed for the stable WSS hostname;
# leave unrelated Cloudflare tunnels (including other projects) unchanged.
$legacy=@(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue|
  Where-Object{$_.Name -eq 'cloudflared.exe' -and
    $_.CommandLine -match 'http://127\.0\.0\.1:8995'})
foreach($p in $legacy){try{Stop-Process -Id $p.ProcessId -Force}catch{}}
$code=$null
try{
  Invoke-WebRequest 'http://127.0.0.1:8995/mcp' -Method POST `
    -ContentType 'application/json' -Body '{}' -TimeoutSec 3|Out-Null
  $code=200
}catch{$code=[int]$_.Exception.Response.StatusCode}
if($code -ne 404){throw ('Obsolete HTTP MCP route is not absent (status '+$code+')')}
Write-Output 'OBSOLETE_MCP_GATEWAY_STOPPED=true'
Write-Output 'NATIVE_PHONE_WSS_RELAY_HEALTHY=true'
Write-Output 'OLD_MCP_HTTP_ENDPOINT_404=true'
Write-Output 'STABLE_SSH_KEY_AND_PAIRING_PRESERVED=true'
Write-Output 'NATIVE_TUNNEL_SUPERVISOR_LAUNCHED_OR_EXISTING=true'
Write-Output ('RETIRED_MODULES_BACKED_UP='+$archive)
