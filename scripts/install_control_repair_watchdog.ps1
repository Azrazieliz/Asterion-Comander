# One-time owner-authorized Windows per-minute service recovery. No administrative privileges needed.
$ErrorActionPreference='Stop'
$path=(Resolve-Path (Join-Path $PSScriptRoot 'control_repair_watchdog.ps1')).Path
$task='Asterion Control Self-Healing Worker'
$cmd='powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File "'+$path+'"'
& schtasks.exe /Create /F /SC MINUTE /MO 1 /TN $task /TR $cmd | Out-Null
if($LASTEXITCODE -ne 0){throw 'Could not install user-context Windows watchdog'}
& schtasks.exe /Run /TN $task | Out-Null
if($LASTEXITCODE -ne 0){throw 'Windows watchdog registered but first execution failed'}
Write-Output 'ASTERION_CONTROL_WATCHDOG_INSTALLED'
