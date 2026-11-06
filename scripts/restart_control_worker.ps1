# Maintenance only. Restarts the existing Asterion Control Windows worker while retaining
# the same private pairing credentials and LAN endpoint. NOT Desktop Commander/ADB.
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$state=Join-Path $env:LOCALAPPDATA 'AsterionControl'
$py=Join-Path $root '.venv\Scripts\python.exe'
$secret=Join-Path $state 'control-token.txt'
if(-not(Test-Path $secret)){throw 'Existing Asterion worker key missing'}
if(-not(Test-Path $py)){throw 'Asterion worker Python missing'}
$env:ASTERION_API_TOKEN=(Get-Content $secret -Raw).Trim()
$env:ASTERION_CONTROL_STATE=$state
$env:ASTERION_REMOTE_ROOT=$HOME
$env:ASTERION_ALLOW_SHELL='1'
$env:ASTERION_ENABLE_DISCOVERY='1'
$hostFile=Join-Path $state 'agent-host.txt'
if(-not(Test-Path $hostFile)){throw 'Native Control endpoint unavailable'}
$endpoint=(Get-Content $hostFile -Raw).Trim()
if($endpoint -notmatch '^http://([0-9.]+):8911
Set-Location $root
# Match only the existing Control app server, never unrelated Python agents.
$old=@(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
  Where-Object { $_.CommandLine -match 'uvicorn\s+asterion_remote\.app:app' })
foreach($p in $old){ Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Milliseconds 900
$out=Join-Path $state 'control-worker.stdout.log'
$err=Join-Path $state 'control-worker.stderr.log'
$server=Start-Process -FilePath $py -ArgumentList '-m','uvicorn','asterion_remote.app:app','--host',$env:ASTERION_LAN_IP,'--port','8911' -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput $out -RedirectStandardError $err
$ok=$false
for($i=0;$i -lt 25;$i++){
  Start-Sleep -Milliseconds 500
  try{
    $health=Invoke-RestMethod ($endpoint+'/api/v1/health') -Headers @{Authorization=('Bearer '+$env:ASTERION_API_TOKEN)} -TimeoutSec 2
    if($health.ok){$ok=$true;break}
  }catch{}
}
if(-not $ok){throw ('Asterion worker could not restart: '+((Get-Content $err -Tail 10 -ErrorAction SilentlyContinue)-join ' | '))}
Write-Output ('CONTROL_WORKER_RESTARTED PID='+$server.Id+' VERSION='+$health.version)
){throw 'Invalid native Control endpoint'}
$env:ASTERION_LAN_IP=$Matches[1]
Set-Location $root
# Match only the existing Control app server, never unrelated Python agents.
$old=@(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
  Where-Object { $_.CommandLine -match 'uvicorn\s+asterion_remote\.app:app' })
foreach($p in $old){ Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Milliseconds 900
$out=Join-Path $state 'control-worker.stdout.log'
$err=Join-Path $state 'control-worker.stderr.log'
$server=Start-Process -FilePath $py -ArgumentList '-m','uvicorn','asterion_remote.app:app','--host','192.168.1.133','--port','8911' -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput $out -RedirectStandardError $err
$ok=$false
for($i=0;$i -lt 25;$i++){
  Start-Sleep -Milliseconds 500
  try{
    $health=Invoke-RestMethod 'http://192.168.1.133:8911/api/v1/health' -Headers @{Authorization=('Bearer '+$env:ASTERION_API_TOKEN)} -TimeoutSec 2
    if($health.ok){$ok=$true;break}
  }catch{}
}
if(-not $ok){throw ('Asterion worker could not restart: '+((Get-Content $err -Tail 10 -ErrorAction SilentlyContinue)-join ' | '))}
Write-Output ('CONTROL_WORKER_RESTARTED PID='+$server.Id+' VERSION='+$health.version)
