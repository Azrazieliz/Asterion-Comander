# Deploy low-latency native screen/input transport on the user's Windows worker.
# Invoked as a one-shot through Asterion Control. No ADB or Desktop Commander.
$ErrorActionPreference='Stop'
$root='D:\AsterionControlRelease'
if(-not(Test-Path $root)){throw 'Existing Control release folder missing'}
Set-Location $root
$dirty=@(git status --porcelain --untracked-files=no)
if($dirty.Count -gt 0){throw 'Tracked working files modified: refusing overwrite'}
git fetch --quiet origin main
if($LASTEXITCODE -ne 0){throw 'Could not fetch canonical source'}
git reset --hard origin/main
if($LASTEXITCODE -ne 0){throw 'Source update failed'}
$python=Join-Path $root '.venv\Scripts\python.exe'
if(-not(Test-Path $python)){throw 'Control Python environment missing'}
# WebSocket dependency is required for both the Uvicorn service and test client.
$ErrorActionPreference='Continue'
& $python -m pip install 'websockets>=14,<17' > (Join-Path $root 'REALTIME_DEPS.log') 2>&1
$depsExit=$LASTEXITCODE
$ErrorActionPreference='Stop'
if($depsExit -ne 0){throw 'WebSocket dependency installation failed'}
& $python -m py_compile 'asterion_remote\live_stream.py' 'scripts\benchmark_native_realtime.py'
if($LASTEXITCODE -ne 0){throw 'Python syntax invalid'}
$node=Get-Command node -ErrorAction SilentlyContinue
if($node){
  & $node.Source --check 'asterion_remote\static\app.js'
  if($LASTEXITCODE -ne 0){throw 'Browser control JS syntax invalid'}
  Write-Output 'JS_SYNTAX_OK'
}else{Write-Output 'JS_SYNTAX_NOT_CHECKED_NO_NODE'}
# Run the backend tests in a private temp directory to avoid unrelated filesystem issues.
$env:ASTERION_API_TOKEN=(Get-Content (Join-Path $env:LOCALAPPDATA 'AsterionControl\control-token.txt') -Raw).Trim()
$env:ASTERION_CONTROL_STATE=Join-Path $env:LOCALAPPDATA 'AsterionControl'
$env:ASTERION_REMOTE_ROOT=$HOME
$env:ASTERION_ALLOW_SHELL='1'
$env:TEMP=Join-Path $root 'test-temp'
$env:TMP=$env:TEMP
New-Item -ItemType Directory -Path $env:TEMP -Force|Out-Null
$ErrorActionPreference='Continue'
& $python -m pytest -q tests/test_live_native_ws.py > (Join-Path $root 'REALTIME_TEST.log') 2>&1
$testExit=$LASTEXITCODE
$ErrorActionPreference='Stop'
if($testExit -ne 0){
  Get-Content (Join-Path $root 'REALTIME_TEST.log') -Tail 50
  throw 'Full-duplex WebSocket tests failed'
}
Write-Output 'NATIVE_WEBSOCKET_TESTS_OK'
# Restart in a detached process so the currently running command can finish.
$restart=Join-Path $root 'scripts\restart_windows_agent.ps1'
Start-Process powershell.exe -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass',
  '-File',('"'+$restart+'"') -WorkingDirectory $root -WindowStyle Hidden
Write-Output ('REALTIME_TRANSPORT_DEPLOYED commit='+(git rev-parse --short HEAD))
Write-Output 'RESTART_SCHEDULED'
