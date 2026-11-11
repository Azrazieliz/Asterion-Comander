# Independently self-heal the Windows worker if unavailable, even when Android cannot reach it.
$ErrorActionPreference='Continue'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$state=Join-Path $env:LOCALAPPDATA 'AsterionControl'
$hostFile=Join-Path $state 'agent-host.txt'
$key=Join-Path $state 'control-token.txt'
if(-not(Test-Path $hostFile) -or -not(Test-Path $key)){exit 1}
$url=(Get-Content $hostFile -Raw).Trim()
$token=(Get-Content $key -Raw).Trim()
if($url -notmatch '^http://[0-9.]+:8911$' -or $token.Length -lt 32){exit 2}
try{
  $health=Invoke-RestMethod ($url+'/api/v1/health') -Headers @{Authorization=('Bearer '+$token)} -TimeoutSec 2
  if($health.ok){exit 0}
}catch{}
# Prefer the existing supervisor; never start duplicates or kill unknown/active processes.
$supervisor=@(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue|Where-Object {$_.Name -match 'powershell' -and $_.CommandLine -match '(?i)start_windows.ps1'})
if($supervisor.Count -gt 0){exit 0}
$listener=@(Get-NetTCPConnection -State Listen -LocalPort 8911 -ErrorAction SilentlyContinue)
if($listener.Count -gt 0){exit 3} # Occupied listener: explicit force repair required
$script=Join-Path $PSScriptRoot 'start_windows.ps1'
if(-not(Test-Path $script)){exit 4}
Start-Process powershell.exe -ArgumentList @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',('"'+$script+'"')) -WindowStyle Hidden -WorkingDirectory $root|Out-Null
exit 0
