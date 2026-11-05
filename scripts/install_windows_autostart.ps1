# Per-user login autostart. No administrator privilege required.
$ErrorActionPreference='Stop'
$launcher=(Resolve-Path (Join-Path $PSScriptRoot 'start_windows.ps1')).Path
$startup=[Environment]::GetFolderPath('Startup')
if(-not(Test-Path $startup)){New-Item -ItemType Directory -Path $startup -Force | Out-Null}
$destination=Join-Path $startup 'Asterion Control Agent.lnk'
$shell=New-Object -ComObject WScript.Shell
$link=$shell.CreateShortcut($destination)
$link.TargetPath=(Get-Command powershell.exe).Source
$link.Arguments='-NoProfile -ExecutionPolicy Bypass -WindowStyle Minimized -File "'+$launcher+'"'
$link.WorkingDirectory=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$link.Description='Independent Asterion Control Windows agent (no Desktop Commander)'
$link.Save()
Write-Host ('Asterion Control login autostart installed: '+$destination)
