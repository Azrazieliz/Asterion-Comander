# One-time Windows installation and login autostart.
$ErrorActionPreference='Stop'
Set-Location (Join-Path $PSScriptRoot '..')
& (Join-Path $PSScriptRoot 'install_windows_autostart.ps1')
$firewall=(Resolve-Path (Join-Path $PSScriptRoot 'enable_private_firewall.ps1')).Path
Write-Host 'Approve the Windows firewall authorization prompt once.'
$process=Start-Process powershell.exe -Verb RunAs -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"'+$firewall+'"')) -Wait -PassThru
if($process.ExitCode -ne 0){Write-Warning 'Private firewall approval failed. Discovery may be unavailable.'}
$start=(Resolve-Path (Join-Path $PSScriptRoot 'start_windows.ps1')).Path
Start-Process powershell.exe -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"'+$start+'"'))
Write-Host 'Asterion Control started. Pair from your Android application.'
