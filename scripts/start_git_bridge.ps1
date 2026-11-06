# Asterion Control-owned Windows private transport watchdog.
# A single owner-authorized worker is allowed; no Desktop Commander or ADB.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $root '.venv\Scripts\python.exe'
$state = Join-Path $env:LOCALAPPDATA 'AsterionControl'
if (-not (Test-Path $python)) { throw 'Asterion Control Python environment unavailable' }
if (-not (Test-Path $state)) { New-Item -ItemType Directory -Path $state -Force | Out-Null }
$log = Join-Path $state 'control-git-bridge-watchdog.log'
$out = Join-Path $state 'control-git-bridge.stdout.log'
$err = Join-Path $state 'control-git-bridge.stderr.log'
$mutex = New-Object System.Threading.Mutex($false, 'Local\AsterionControlGitBridge')
$owned = $false
try {
  try { $owned = $mutex.WaitOne(0) }
  catch [System.Threading.AbandonedMutexException] { $owned = $true }
  if (-not $owned) { Write-Output 'CONTROL_GIT_BRIDGE_ALREADY_RUNNING'; exit 0 }
  $backoff = 5
  while ($true) {
    try {
      Set-Location $root
      $env:ASTERION_CONTROL_HOST = if ($env:ASTERION_CONTROL_HOST) {
        $env:ASTERION_CONTROL_HOST
      } else { 'http://192.168.1.133:8911' }
      $worker = Start-Process -FilePath $python -ArgumentList '-m','asterion_remote.github_bridge_git' -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput $out -RedirectStandardError $err
      if (-not $worker) { throw 'Native Control transport failed to launch' }
      Add-Content -Path $log -Value ("START " + (Get-Date -Format 'o') + " PID=" + $worker.Id)
      $worker.WaitForExit()
      Add-Content -Path $log -Value ("EXIT " + (Get-Date -Format 'o') + " CODE=" + $worker.ExitCode)
    } catch {
      Add-Content -Path $log -Value ("ERROR " + (Get-Date -Format 'o') + " " + $_.Exception.GetType().Name)
    }
    # Stop log accumulation if the process repeatedly fails over multiple days.
    if ((Test-Path $log) -and (Get-Item $log).Length -gt 1048576) {
      Get-Content $log -Tail 1000 | Set-Content $log -Encoding ASCII
    }
    Start-Sleep -Seconds $backoff
    $backoff = [Math]::Min($backoff + 5, 45)
  }
} finally {
  if ($owned) { $mutex.ReleaseMutex() }
  $mutex.Dispose()
}
