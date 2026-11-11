# Full-path repair of the EXISTING native Windows worker -> Android agent -> direct WebSocket.
# No new MCP connector, no device re-pair, no credential rotation, no project cleanup.
param([ValidateSet('auto','force')][string]$Mode='auto',
      [ValidatePattern('^[0-9a-f]{32}$')][string]$RepairId)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$state=Join-Path $env:LOCALAPPDATA 'AsterionControl'
$report=Join-Path $state 'full-repair.json'
$steps=[ordered]@{}
function Write-Receipt([string]$phase,[bool]$ok,[string]$error='') {
  $object=[ordered]@{id=$RepairId;mode=$Mode;phase=$phase;ok=$ok;
    updated=([DateTimeOffset]::UtcNow.ToUnixTimeSeconds());steps=$steps;error=$error}
  $tmp=$report+'.new'
  [System.IO.File]::WriteAllText($tmp,($object|ConvertTo-Json -Depth 6 -Compress),
    (New-Object System.Text.UTF8Encoding($false)))
  Move-Item -LiteralPath $tmp -Destination $report -Force
}
function Worker-Health($url,$token) {
  try {
    $result=Invoke-RestMethod ($url+'/api/v1/health') -Headers @{Authorization=('Bearer '+$token)} -TimeoutSec 3
    return [bool]$result.ok
  }catch{return $false}
}
function Phone-Probe($url,$token) {
  try{
    return Invoke-RestMethod ($url+'/api/v1/phone') -Headers @{Authorization=('Bearer '+$token)} -TimeoutSec 5
  }catch{return $null}
}
try {
  $secret=Join-Path $state 'control-token.txt'
  $hostFile=Join-Path $state 'agent-host.txt'
  if(-not(Test-Path $secret) -or -not(Test-Path $hostFile)){
    throw 'Saved native worker pairing unavailable; credentials preserved'
  }
  $token=(Get-Content $secret -Raw).Trim()
  $url=(Get-Content $hostFile -Raw).Trim()
  if($token.Length -lt 32 -or $url -notmatch '^http://[0-9.]+:8911$'){
    throw 'Saved worker address or authorization invalid; no reset performed'
  }
  $worker=Worker-Health $url $token
  if(-not $worker){
    $supervisors=@(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
      Where-Object {$_.Name -match 'powershell' -and $_.CommandLine -match '(?i)start_windows.ps1'})
    if($supervisors.Count -eq 0){
      $runner=Join-Path $PSScriptRoot 'start_windows.ps1'
      if(-not(Test-Path $runner)){throw 'Native Windows worker supervisor not installed'}
      Start-Process powershell.exe -ArgumentList @('-NoProfile','-NonInteractive',
        '-ExecutionPolicy','Bypass','-File',('"'+$runner+'"')) -WorkingDirectory $root -WindowStyle Hidden | Out-Null
    }
    for($i=0;$i -lt 14;$i++){
      Start-Sleep -Milliseconds 500
      if(Worker-Health $url $token){$worker=$true;break}
    }
  }
  $steps['windows_worker']=if($worker){'verified'}else{'unreachable'}
  Write-Receipt 'running' $false
  $phone=$null
  if($worker){
    # The Android app is also re-registering its EXISTING phone listener.
    for($i=0;$i -lt 9;$i++){
      $phone=Phone-Probe $url $token
      if($phone -and $phone.paired -and $phone.reachable){break}
      Start-Sleep -Milliseconds 800
    }
  }
  $ready=[bool]($phone -and $phone.paired -and $phone.reachable)
  $steps['phone_listener']=if($ready){'verified'}else{'unreachable'}
  $direct=$false
  $accessible=$false
  $capture=$false
  if($ready){
    $accessible=[bool]$phone.info.accessible
    $capture=[bool]$phone.info.capture
    $transport=$phone.info.remote_transport.direct_mcp
    # Historical internal field name is "direct_mcp"; it reports the existing native WSS.
    $direct=[bool]($transport.connected -and $transport.transport -eq 'direct_wss')
  }
  $steps['native_websocket']=if($direct){'verified'}else{'not_connected'}
  $steps['accessibility']=if($accessible){'verified'}else{'android_permission_required'}
  $steps['live_video']=if($capture){'capture_active'}else{'android_media_projection_consent_required'}
  $steps['existing_update_feed']='preserved'
  $steps['private_fallback']='untouched'
  Write-Receipt 'running' $false
  if($Mode -eq 'force'){
    # Restart the SAME authorized Windows worker independently after the repair API
    # request finishes. Existing restart script refuses to interrupt active jobs.
    $launcher=Join-Path $PSScriptRoot 'control_finalize_restart.ps1'
    if(-not(Test-Path $launcher)){throw 'Safe Windows restart finalizer not present'}
    Start-Process powershell.exe -ArgumentList @('-NoProfile','-NonInteractive',
      '-ExecutionPolicy','Bypass','-File',('"'+$launcher+'"'),'-RepairId',$RepairId) `
      -WorkingDirectory $root -WindowStyle Hidden | Out-Null
    $steps['windows_restart']='scheduled_only_when_idle'
    Write-Receipt 'restarting' $false
    exit 0
  }
  $verified=$worker -and $ready -and $direct -and $accessible -and $capture
  if($verified){Write-Receipt 'verified' $true}
  elseif($worker -and $ready -and $direct -and $accessible -and -not $capture){
    Write-Receipt 'permission_required' $false 'Android must approve screen sharing'
  }else{
    Write-Receipt 'partial' $false 'Not every native Control component was verified'
  }
}catch{
  $steps['preservation']='No credentials, user files or app data were cleared'
  Write-Receipt 'failed' $false $_.Exception.Message
  exit 1
}
