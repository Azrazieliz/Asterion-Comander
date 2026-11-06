# Maintenance: restart the existing native Control Windows agent only.
# This script never invokes Desktop Commander, ADB or a second remote provider.
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$state=Join-Path $env:LOCALAPPDATA 'AsterionControl'
$python=Join-Path $root '.venv\Scripts\python.exe'
$secret=Join-Path $state 'control-token.txt'
$hostFile=Join-Path $state 'agent-host.txt'
if(-not(Test-Path $secret)){throw 'Native Control pairing credential missing'}
if(-not(Test-Path $python)){throw 'Native Control Python environment missing'}
if(-not(Test-Path $hostFile)){throw 'Native Control endpoint state missing'}
$endpoint=(Get-Content $hostFile -Raw).Trim()
if($endpoint -notmatch '^http://([0-9.]+):8911$'){
  throw 'Invalid native Control endpoint'
}
$ip=$Matches[1]
$env:ASTERION_API_TOKEN=(Get-Content $secret -Raw).Trim()
$env:ASTERION_CONTROL_STATE=$state
$env:ASTERION_REMOTE_ROOT=$HOME
$env:ASTERION_ALLOW_SHELL='1'
$env:ASTERION_ENABLE_DISCOVERY='1'
Set-Location $root
$workers=@(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
  Where-Object {$_.CommandLine -match 'uvicorn\s+asterion_remote\.app:app'})
# Never interrupt a running build, transfer or other authorized Control job.
try{
  $running=Invoke-RestMethod ($endpoint+'/api/v1/commands') -Headers @{
    Authorization=('Bearer '+$env:ASTERION_API_TOKEN)
  } -TimeoutSec 3
  if(@($running.items | Where-Object {$_.status -eq 'running'}).Count -gt 0){
    throw 'Active Control jobs: restart must wait until they finish'
  }
}catch{
  if($_.Exception.Message -match '^Active Control jobs'){throw}
  if($workers.Count -gt 0){throw 'Cannot verify Control is idle; refusing risky restart'}
}
foreach($worker in $workers){Stop-Process -Id $worker.ProcessId -Force -ErrorAction Stop}
Start-Sleep -Milliseconds 900
# A separately running Control supervisor may have already brought it back.
try{
  $health=Invoke-RestMethod ($endpoint+'/api/v1/health') -Headers @{
    Authorization=('Bearer '+$env:ASTERION_API_TOKEN)
  } -TimeoutSec 2
  if($health.ok){Write-Output 'CONTROL_ALREADY_RECOVERED';exit 0}
}catch{}
$out=Join-Path $state 'control-worker.stdout.log'
$err=Join-Path $state 'control-worker.stderr.log'
$worker=Start-Process -FilePath $python -ArgumentList @(
  '-m','uvicorn','asterion_remote.app:app','--host',$ip,'--port','8911'
) -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput $out -RedirectStandardError $err
for($i=0;$i -lt 25;$i++){
  Start-Sleep -Milliseconds 500
  try{
    $health=Invoke-RestMethod ($endpoint+'/api/v1/health') -Headers @{
      Authorization=('Bearer '+$env:ASTERION_API_TOKEN)
    } -TimeoutSec 2
    if($health.ok){
      Write-Output ('CONTROL_WORKER_RESTARTED PID='+$worker.Id)
      exit 0
    }
  }catch{}
}
throw 'Native Control worker failed to restart; inspect private logs'
