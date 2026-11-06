# Supervise ONLY Asterion Control's own private command transport.
# No Desktop Commander, ADB or additional remote-control provider.
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python=Join-Path $root '.venv\Scripts\python.exe'
$state=Join-Path $env:LOCALAPPDATA 'AsterionControl'
if(-not(Test-Path $python)){throw 'Native Control Python environment missing'}
New-Item -ItemType Directory -Path $state -Force | Out-Null
$log=Join-Path $state 'control-git-bridge-watchdog.log'
$out=Join-Path $state 'control-git-bridge.stdout.log'
$err=Join-Path $state 'control-git-bridge.stderr.log'
$mutex=New-Object System.Threading.Mutex($false,'Local\AsterionControlGitBridge')
$owned=$false
try {
  try{$owned=$mutex.WaitOne(0)}
  catch [System.Threading.AbandonedMutexException]{$owned=$true}
  if(-not $owned){Write-Output 'CONTROL_GIT_BRIDGE_ALREADY_RUNNING';exit 0}
  $backoff=5
  while($true){
    try{
      Set-Location $root
      # Never run two workers against the same private command queue.
      $existing=@(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
        Where-Object {$_.CommandLine -match 'asterion_remote\.github_bridge_git'})
      if($existing.Count -gt 0){
        Add-Content $log ('EXISTING_WORKER '+(Get-Date -Format 'o'))
        Start-Sleep -Seconds 20
        continue
      }
      $hostFile=Join-Path $state 'agent-host.txt'
      if(-not(Test-Path $hostFile)){
        Add-Content $log 'WAIT_NATIVE_CONTROL_ENDPOINT'
        Start-Sleep -Seconds 5
        continue
      }
      $selected=(Get-Content $hostFile -Raw).Trim()
      if($selected -notmatch '^http://[0-9.]+:8911$'){
        throw 'Stored native Control endpoint invalid'
      }
      $env:ASTERION_CONTROL_HOST=$selected
      $worker=Start-Process -FilePath $python -ArgumentList @(
        '-m','asterion_remote.github_bridge_git'
      ) -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput $out -RedirectStandardError $err
      if(-not $worker){throw 'Native Control bridge launch failed'}
      Add-Content $log ('START '+(Get-Date -Format 'o')+' PID='+$worker.Id)
      $worker.WaitForExit()
      Add-Content $log ('EXIT '+(Get-Date -Format 'o')+' CODE='+$worker.ExitCode)
    }catch{
      Add-Content $log ('ERROR '+(Get-Date -Format 'o')+' '+$_.Exception.GetType().Name)
    }
    if((Test-Path $log) -and (Get-Item $log).Length -gt 1048576){
      $tmp=$log+'.old'
      Move-Item -Path $log -Destination $tmp -Force
      Remove-Item $tmp -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds $backoff
    $backoff=[Math]::Min($backoff+5,45)
  }
}finally{
  if($owned){$mutex.ReleaseMutex()}
  $mutex.Dispose()
}
