$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
$venv = '.\.venv\Scripts\python.exe'
if (-not (Test-Path $venv)) { py -3 -m venv .venv }
& $venv -m pip install -r requirements.txt
$settings = Join-Path $env:LOCALAPPDATA 'AsterionRemote'
New-Item -ItemType Directory -Path $settings -Force | Out-Null
$secret = Join-Path $settings 'token.txt'
if (-not (Test-Path $secret)) {
  (& $venv -c 'import secrets; print(secrets.token_urlsafe(40))') | Set-Content -Path $secret -NoNewline
}
$env:ASTERION_API_TOKEN = (Get-Content $secret -Raw).Trim()
if (-not $env:ASTERION_REMOTE_ROOT) { $env:ASTERION_REMOTE_ROOT = $HOME }
if (-not $env:ASTERION_ALLOW_SHELL) { $env:ASTERION_ALLOW_SHELL = '1' }
if (-not $env:ASTERION_ALLOW_ANDROID_SHELL) { $env:ASTERION_ALLOW_ANDROID_SHELL = '1' }
Write-Host ''
Write-Host 'ASTERION REMOTE STARTED (no Desktop Commander account)' -ForegroundColor Cyan
Write-Host 'Open on this PC: http://127.0.0.1:8911'
Write-Host "API token: $env:ASTERION_API_TOKEN"
Write-Host "Token saved in your Windows profile: $secret"
Write-Host 'Control from another device using an authenticated private network tunnel.'
Write-Host ''
& $venv -m uvicorn asterion_remote.app:app --host 127.0.0.1 --port 8911
