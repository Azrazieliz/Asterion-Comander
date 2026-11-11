# Safe independent worker reload after an API-triggered maintenance command has exited.
Start-Sleep -Seconds 8
$ErrorActionPreference='Stop'
$log=Join-Path $env:LOCALAPPDATA 'AsterionControl\restart-recovery.log'
try {
  & (Join-Path $PSScriptRoot 'restart_control_worker.ps1') *> $log
} catch {
  Add-Content -LiteralPath $log -Value ('RECOVERY_RESTART_FAILED '+$_.Exception.GetType().Name)
  exit 1
}
