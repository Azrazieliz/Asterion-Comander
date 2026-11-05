# Private Asterion Control bridge: ChatGPT command fallback, not the main controller.
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root
$py=Join-Path $root '.venv\Scripts\python.exe'
if(-not(Test-Path $py)){throw 'Asterion Control Python environment unavailable'}
$env:ASTERION_CONTROL_HOST=if($env:ASTERION_CONTROL_HOST){$env:ASTERION_CONTROL_HOST}else{'http://192.168.1.133:8911'}
& $py -m asterion_remote.github_bridge_git
