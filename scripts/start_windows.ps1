# Asterion Control Windows agent. Android is the primary interface.
# LAN only; use an encrypted private tunnel for access across networks.
$ErrorActionPreference='Stop'
Set-Location (Join-Path $PSScriptRoot '..')
$venv='.\.venv\Scripts\python.exe'
if (-not (Test-Path $venv)) { py -3 -m venv .venv }
if (-not (Test-Path $venv)) {throw 'Python environment unavailable'}
if (-not (Test-Path '.venv\.asterion-deps-ready')) {
  & $venv -m pip install -r requirements.txt
  if ($LASTEXITCODE -ne 0) {throw 'Dependency installation failed'}
  Set-Content -Path '.venv\.asterion-deps-ready' -Value '1'
}
$settings=Join-Path $env:LOCALAPPDATA 'AsterionControl'
New-Item -ItemType Directory -Path $settings -Force | Out-Null
$secret=Join-Path $settings 'control-token.txt'
if (-not (Test-Path $secret)) {
  (& $venv -c 'import secrets;print(secrets.token_urlsafe(48))') | Set-Content $secret -NoNewline
}
$env:ASTERION_API_TOKEN=(Get-Content $secret -Raw).Trim()
$env:ASTERION_CONTROL_STATE=$settings
$env:ASTERION_ENABLE_DISCOVERY='1'
if (-not $env:ASTERION_REMOTE_ROOT) {$env:ASTERION_REMOTE_ROOT=$HOME}
$env:ASTERION_ALLOW_SHELL='1'
$addresses=Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object {
  $_.AddressState -eq 'Preferred' -and $_.IPAddress -notlike '169.254.*' -and
  ($_.IPAddress -like '192.168.*' -or $_.IPAddress -like '10.*' -or $_.IPAddress -like '172.*' -or $_.IPAddress -like '100.*')
}
$bind=if($env:ASTERION_LAN_IP){$env:ASTERION_LAN_IP}elseif($addresses){@($addresses)[0].IPAddress}else{'127.0.0.1'}
Write-Host ('Asterion Control | Windows agent '+$bind+':8911')
Write-Host 'Find your PC from Android. Use the one-time code below for first pairing only.'
$pinFile=Join-Path $settings 'pairing-code.txt'
Remove-Item $pinFile -ErrorAction SilentlyContinue
$job=Start-Process -FilePath $venv -ArgumentList '-m','uvicorn','asterion_remote.app:app','--host',$bind,'--port','8911' -NoNewWindow -PassThru
for($n=0;$n -lt 30;$n++){
  if(Test-Path $pinFile){Write-Host ('ONE-TIME PAIRING CODE: '+(Get-Content $pinFile -Raw)) -ForegroundColor Cyan;break}
  Start-Sleep -Milliseconds 200
}
if(-not(Test-Path $pinFile)){Write-Warning 'Pairing code not yet available. Check the server startup log.'}
Wait-Process -Id $job.Id
