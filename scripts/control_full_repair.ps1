# Asterion Control, user-invoked full-path repair. No reinstall, re-pair, token changes or project reset.
param([ValidateSet('auto','force')][string]$Mode='auto',[string]$RepairId='')
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$state=Join-Path $env:LOCALAPPDATA 'AsterionControl'
$report=Join-Path $state 'full-repair.json'
$steps=[ordered]@{}
$started=Get-Date
if(-not(Test-Path $state)){New-Item -ItemType Directory -Path $state -Force|Out-Null}
function Report([string]$phase,[bool]$ok,[string]$error=''){
  $data=[ordered]@{id=$RepairId;phase=$phase;mode=$Mode;ok=$ok;updated=([DateTimeOffset]::UtcNow.ToUnixTimeSeconds());steps=$steps;error=$error}
  $tmp=$report+'.new'
  $json=$data|ConvertTo-Json -Depth 8 -Compress
  [System.IO.File]::WriteAllText($tmp,$json,(New-Object System.Text.UTF8Encoding($false)))
  Move-Item -LiteralPath $tmp -Destination $report -Force
}
function Health([string]$url,[string]$token){
  try{
    $r=Invoke-RestMethod ($url+'/api/v1/health') -Headers @{Authorization=('Bearer '+$token)} -TimeoutSec 2
    return [bool]$r.ok
  }catch{return $false}
}
function Gateway(){
  foreach($port in @(8995,8996)){
    try {
      $v=Invoke-RestMethod ('http://127.0.0.1:'+ $port +'/healthz') -TimeoutSec 2
      if($v.ok -and $v.service -match 'asterion'){return $port}
    }catch{}
  }
  return 0
}
function Wait-Gateway([int]$attempts){
  for($n=0;$n -lt $attempts;$n++){
    $port=Gateway
    if($port -gt 0){return $port}
    Start-Sleep -Milliseconds 500
  }
  return 0
}
function Wait-Worker([string]$url,[string]$token,[int]$attempts){
  for($n=0;$n -lt $attempts;$n++){
    if(Health $url $token){return $true}
    Start-Sleep -Milliseconds 500
  }
  return $false
}
function Start-DetachedScript([string]$name){
  $file=Join-Path $PSScriptRoot $name
  if(-not(Test-Path $file)){throw ('Missing recovery component '+$name)}
  Start-Process powershell.exe -ArgumentList @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',('"'+$file+'"')) -WorkingDirectory $root -WindowStyle Hidden|Out-Null
}
try{
  $secretFile=Join-Path $state 'control-token.txt'
  $endpointFile=Join-Path $state 'agent-host.txt'
  if(-not(Test-Path $secretFile) -or -not(Test-Path $endpointFile)){throw 'Original Windows pairing or endpoint unavailable; existing settings preserved'}
  $token=(Get-Content $secretFile -Raw).Trim()
  $url=(Get-Content $endpointFile -Raw).Trim()
  if($token.Length -lt 32 -or $url -notmatch '^http://[0-9.]+:8911$'){throw 'Saved Windows worker configuration invalid; no credentials were reset'}
  # Independent persistent supervisor keeps the primary worker alive after this request completes.
  $supervisor=@(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue|Where-Object {$_.Name -match 'powershell' -and $_.CommandLine -match '(?i)start_windows.ps1'})
  if(-not $supervisor){
    Start-DetachedScript 'start_windows.ps1'
    $steps['worker_supervisor']='started'
  }else{$steps['worker_supervisor']='running'}
  $worker=Wait-Worker $url $token 12
  $steps['windows_worker']=if($worker){'verified'}else{'unreachable; supervisor recovery pending'}
  Report 'running' $false
  # Gateway is the direct ChatGPT transport. Do not rotate its key, replace an unrelated listener or create a new paid dependency.
  $port=Gateway
  if($port -eq 0){
    $key=Join-Path $state 'mcp-gateway-token.txt'
    $python=Join-Path $root '.venv\Scripts\python.exe'
    $reserved=@(Get-NetTCPConnection -State Listen -LocalPort 8995,8996 -ErrorAction SilentlyContinue)
    if($reserved.Count -gt 0){$steps['direct_mcp_gateway']='blocked: reserved port, no replacement attempted'}
    elseif(-not(Test-Path $key) -or -not(Test-Path $python)){$steps['direct_mcp_gateway']='blocked: existing MCP credentials/runtime missing'}
    else{
      $stdout=Join-Path $state 'mcp-repair.stdout.log'
      $stderr=Join-Path $state 'mcp-repair.stderr.log'
      Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','asterion_remote.mcp_gateway:app','--host','127.0.0.1','--port','8995') -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr | Out-Null
      $port=Wait-Gateway 15
      $steps['direct_mcp_gateway']=if($port -gt 0){'verified: local '+$port}else{'not responding after restart'}
    }
  }else{$steps['direct_mcp_gateway']='verified: local '+$port}
  # Restore only an already consented stable HTTPS Funnel. Never overwrite a different service or rotate tunnel identity.
  $funnelFlag=Join-Path $state 'mcp-persistent-enabled.flag'
  if(Test-Path $funnelFlag){
    $funnel=Join-Path $PSScriptRoot 'start_persistent_mcp_funnel.ps1'
    if(Test-Path $funnel){
      try{
        $proc=Start-Process powershell.exe -ArgumentList @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',('"'+$funnel+'"')) -WorkingDirectory $root -WindowStyle Hidden -Wait -PassThru
        $steps['stable_https_tunnel']=if($proc.ExitCode -eq 0){'revalidated'}else{'failed: preserved current configuration'}
      }catch{$steps['stable_https_tunnel']='failed: '+$_.Exception.GetType().Name}
    }else{$steps['stable_https_tunnel']='missing stable funnel script'}
  }else{$steps['stable_https_tunnel']='not previously enabled: not altered'}
  Report 'running' $false
  # GitHub is a fallback, never the primary real-time control channel.
  $bridge=@(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {$_.Name -match 'python' -and $_.CommandLine -match 'asterion_remote.github_bridge_git'})
  if($bridge.Count -eq 0){
    try{Start-DetachedScript 'start_git_bridge.ps1';$steps['private_fallback']='restart requested'}
    catch{$steps['private_fallback']='unavailable: '+$_.Exception.GetType().Name}
  }else{$steps['private_fallback']='running'}
  # Windows worker itself verifies phone agent with its saved private credentials. No re-pairing.
  if($worker){
    try{
      $phone=Invoke-RestMethod ($url+'/api/v1/phone') -Headers @{Authorization=('Bearer '+$token)} -TimeoutSec 4
      if($phone.paired -and $phone.reachable){$steps['phone_agent']='verified'}
      elseif($phone.paired){$steps['phone_agent']='registered but unreachable; Android repair/re-registration required'}
      else{$steps['phone_agent']='not registered; Android repair/re-registration required'}
    }catch{$steps['phone_agent']='verification unavailable: '+$_.Exception.GetType().Name}
  }else{$steps['phone_agent']='not checked: worker offline'}
  # A separate quick web response is not proof of fresh screen frames or direct ChatGPT tool exposure.
  $steps['native_live_screen']='requires fresh Android MediaProjection frame and stream-client receipt'
  $steps['chatgpt_direct_tool']='requires current ChatGPT connector invocation; worker cannot enroll ChatGPT tools'
  if($Mode -eq 'force'){
    # Scheduled after this process, by an independent worker supervisor.
    # Existing restart script refuses to interrupt active jobs and preserves pairing.
    try{
      $restart=Join-Path $PSScriptRoot 'restart_control_worker.ps1'
      if(-not(Test-Path $restart)){throw 'safe Windows restart script missing'}
      $launcher='Start-Sleep -Seconds 4; & '+('"' + $restart + '"')
      Start-Process powershell.exe -ArgumentList @('-NoProfile','-NonInteractive','-Command',('"'+$launcher+'"')) -WindowStyle Hidden -WorkingDirectory $root | Out-Null
      $steps['windows_reinitialize']='scheduled safely; verify worker again after restart'
    }catch{$steps['windows_reinitialize']='blocked: '+$_.Exception.GetType().Name}
  }
  $good=$worker -and ($port -gt 0) -and ($steps['phone_agent'] -eq 'verified')
  Report $(if($good){'verified_core'}else{'partial'}) $good
}catch{
  $steps['safe_recovery']='stopped without altering credentials or files'
  Report 'failed' $false $_.Exception.Message
  exit 1
}
