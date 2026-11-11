# Independent full-path Control watchdog, scheduled once/minute by the owner.
# Never delete credentials, re-pair devices, touch user files or replace unrelated services.
$ErrorActionPreference='Continue'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$state=Join-Path $env:LOCALAPPDATA 'AsterionControl'
$hostFile=Join-Path $state 'agent-host.txt'
$key=Join-Path $state 'control-token.txt'
if(-not(Test-Path $hostFile) -or -not(Test-Path $key)){exit 1}
$url=(Get-Content $hostFile -Raw).Trim()
$token=(Get-Content $key -Raw).Trim()
if($url -notmatch '^http://[0-9.]+:8911$' -or $token.Length -lt 32){exit 2}
$workerOk=$false
try{
  $health=Invoke-RestMethod ($url+'/api/v1/health') -Headers @{Authorization=('Bearer '+$token)} -TimeoutSec 2
  $workerOk=[bool]$health.ok
}catch{}
$missesFile=Join-Path $state 'control-watchdog-misses.txt'
$misses=0
if($workerOk){
  Set-Content -LiteralPath $missesFile -Value '0' -NoNewline -Encoding ASCII
}else{
  if(Test-Path $missesFile){[void][int]::TryParse((Get-Content $missesFile -Raw).Trim(),[ref]$misses)}
  $misses=[math]::Min(99,$misses+1)
  Set-Content -LiteralPath $missesFile -Value ([string]$misses) -NoNewline -Encoding ASCII
  if($misses -lt 3){exit 0} # Transient outage: avoid unnecessary restarts.
  $listener=Get-NetTCPConnection -State Listen -LocalPort 8911 -ErrorAction SilentlyContinue|Select-Object -First 1
  if($listener){
    $owner=Get-CimInstance Win32_Process -Filter ('ProcessId='+$listener.OwningProcess) -ErrorAction SilentlyContinue
    # Explicitly target the known Asterion worker only, never an unknown listener.
    if(-not $owner -or $owner.CommandLine -notmatch 'uvicorn\s+asterion_remote\.app:app'){exit 3}
    Stop-Process -Id $owner.ProcessId -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 600
  }
  $supervisor=@(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue|
    Where-Object {$_.Name -match 'powershell' -and $_.CommandLine -match '(?i)start_windows.ps1'})
  if($supervisor.Count -eq 0){
    $launcher=Join-Path $PSScriptRoot 'start_windows.ps1'
    if(-not(Test-Path $launcher)){exit 4}
    Start-Process powershell.exe -ArgumentList @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',('"'+$launcher+'"')) -WindowStyle Hidden -WorkingDirectory $root|Out-Null
  }
  exit 0 # The next scheduled check verifies actual startup, never assume success.
}
# The retired MCP gateway is deliberately NOT monitored, launched, restarted,
# or required. Only the existing Windows worker and private GitHub relay are
# authorized watchdog targets. The phone's native WSS is independent.
$bridge=@(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue|
  Where-Object {$_.Name -match 'python' -and $_.CommandLine -match 'asterion_remote.github_bridge_git'})
if($bridge.Count -eq 0){
  $launch=Join-Path $PSScriptRoot 'start_git_bridge.ps1'
  if(Test-Path $launch){Start-Process powershell.exe -ArgumentList @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',('"'+$launch+'"')) -WorkingDirectory $root -WindowStyle Hidden|Out-Null}
}
exit 0
