# Independent full-path Control watchdog, scheduled once/minute by the owner.
# Never delete credentials, re-pair devices, touch user files or replace unrelated services.
$ErrorActionPreference='Continue'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$state=Join-Path $env:LOCALAPPDATA 'AsterionControl'
$hostFile=Join-Path $state 'agent-host.txt'
$key=Join-Path $state 'control-token.txt'
if(-not(Test-Path $hostFile) -or -not(Test-Path $key)){exit 1}
$url=(Get-Content $hostFile -Raw).Trim()
$token=(Get-Content $key -Raw).Trim()
if($url -notmatch '^http://[0-9.]+:8911$' -or $token.Length -lt 32){exit 2}
$workerOk=$false
try{
  $health=Invoke-RestMethod ($url+'/api/v1/health') -Headers @{Authorization=('Bearer '+$token)} -TimeoutSec 2
  $workerOk=[bool]$health.ok
}catch{}
$missesFile=Join-Path $state 'control-watchdog-misses.txt'
$misses=0
if($workerOk){
  Set-Content -LiteralPath $missesFile -Value '0' -NoNewline -Encoding ASCII
}else{
  if(Test-Path $missesFile){[void][int]::TryParse((Get-Content $missesFile -Raw).Trim(),[ref]$misses)}
  $misses=[math]::Min(99,$misses+1)
  Set-Content -LiteralPath $missesFile -Value ([string]$misses) -NoNewline -Encoding ASCII
  if($misses -lt 3){exit 0} # Transient outage: avoid unnecessary restarts.
  $listener=Get-NetTCPConnection -State Listen -LocalPort 8911 -ErrorAction SilentlyContinue|Select-Object -First 1
  if($listener){
    $owner=Get-CimInstance Win32_Process -Filter ('ProcessId='+$listener.OwningProcess) -ErrorAction SilentlyContinue
    # Explicitly target the known Asterion worker only, never an unknown listener.
    if(-not $owner -or $owner.CommandLine -notmatch 'uvicorn\s+asterion_remote\.app:app'){exit 3}
    Stop-Process -Id $owner.ProcessId -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 600
  }
  $supervisor=@(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue|
    Where-Object {$_.Name -match 'powershell' -and $_.CommandLine -match '(?i)start_windows.ps1'})
  if($supervisor.Count -eq 0){
    $launcher=Join-Path $PSScriptRoot 'start_windows.ps1'
    if(-not(Test-Path $launcher)){exit 4}
    Start-Process powershell.exe -ArgumentList @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',('"'+$launcher+'"')) -WindowStyle Hidden -WorkingDirectory $root|Out-Null
  }
  exit 0 # The next scheduled check verifies actual startup, never assume success.
}
# The retired MCP gateway is deliberately NOT monitored, launched, restarted,
# or required. Only the existing Windows worker and private GitHub relay are
# authorized watchdog targets. The phone's native WSS is independent.
# Keep the original phone-outbound WSS working on the same local port as
# the established stable HTTPS forwarding. This is a MINIMAL native relay:
# /phone/live and /healthz ONLY, never MCP, OAuth or ChatGPT tool discovery.
$nativeRelayOk=$false
try{
  $probe=Invoke-RestMethod 'http://127.0.0.1:8995/healthz' -TimeoutSec 2
  $nativeRelayOk=($probe.ok -and $probe.service -eq 'asterion-native-phone-wss')
}catch{}
if(-not $nativeRelayOk){
  $occupied=@(Get-NetTCPConnection -State Listen -LocalPort 8995 -ErrorAction SilentlyContinue)
  if($occupied.Count -eq 0){
    $python=Join-Path $root '.venv\Scripts\python.exe'
    if(Test-Path $python){
      Start-Process -FilePath $python -ArgumentList @('-m','uvicorn',
        'asterion_remote.native_phone_relay:app','--host','127.0.0.1','--port','8995') `
        -WorkingDirectory $root -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $state 'native-wss.stdout.log') `
        -RedirectStandardError (Join-Path $state 'native-wss.stderr.log')|Out-Null
    }
  }
  # A different service owns 8995: never kill it blindly or claim WSS ready.
}
$nativeFlag=Join-Path $state 'native-wss-enabled.flag'
if(Test-Path $nativeFlag){
  $supervised=@(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue|
    Where-Object{$_.CommandLine -match 'start_native_wss_tunnel\.py'})
  if($supervised.Count -eq 0){
    $python=Join-Path $root '.venv\Scripts\python.exe'
    $script=Join-Path $PSScriptRoot 'start_native_wss_tunnel.py'
    if((Test-Path $python) -and (Test-Path $script)){
      Start-Process -FilePath $python -ArgumentList @($script) -WorkingDirectory $root `
        -WindowStyle Hidden -RedirectStandardOutput (Join-Path $state 'native-wss-tunnel.stdout.log') `
        -RedirectStandardError (Join-Path $state 'native-wss-tunnel.stderr.log')|Out-Null
    }
  }
}
$bridge=@(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue|
  Where-Object {$_.Name -match 'python' -and $_.CommandLine -match 'asterion_remote.github_bridge_git'})
if($bridge.Count -eq 0){
  $launch=Join-Path $PSScriptRoot 'start_git_bridge.ps1'
  if(Test-Path $launch){Start-Process powershell.exe -ArgumentList @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',('"'+$launch+'"')) -WorkingDirectory $root -WindowStyle Hidden|Out-Null}
}

# Native WSS recovery: a running process alone is not proof of a usable phone link.
# Only intervene after two real phone-side handshake rejections while the phone
# remains reachable. Never alter Android permissions, keys, pairing or other services.
$nativeFailuresFile=Join-Path $state 'native-wss-handshake-failures.txt'
try{
  $phone=Invoke-RestMethod ($url+'/api/v1/phone') -Headers @{Authorization=('Bearer '+$token)} -TimeoutSec 3
  $direct=$phone.info.remote_transport.direct_mcp
  $rejected=[bool]($nativeRelayOk -and $phone.reachable -and $direct -and
    -not $direct.connected -and $direct.last_stage -eq 'wss_upgrade' -and
    $direct.last_error_detail -like '*WSS handshake rejected*')
  $failures=0
  if($rejected){
    if(Test-Path $nativeFailuresFile){
      [void][int]::TryParse((Get-Content $nativeFailuresFile -Raw).Trim(),[ref]$failures)
    }
    $failures=[math]::Min(99,$failures+1)
    if($failures -ge 2){
      $local=Invoke-RestMethod 'http://127.0.0.1:8995/healthz' -TimeoutSec 3
      if($local.ok -and -not $local.phone_connected){
        $socket=@(Get-NetTCPConnection -State Listen -LocalPort 8995 -ErrorAction SilentlyContinue)
        if($socket.Count -eq 1){
          $owner=Get-CimInstance Win32_Process -Filter ('ProcessId='+$socket[0].OwningProcess) -ErrorAction SilentlyContinue
          if($owner -and $owner.CommandLine -like '*asterion_remote.native_phone_relay:app*'){
            Stop-Process -Id $owner.ProcessId -Force -ErrorAction Stop
            Start-Sleep -Milliseconds 400
            $python=Join-Path $root '.venv\Scripts\python.exe'
            if(Test-Path $python){
              Start-Process -FilePath $python -ArgumentList @('-m','uvicorn',
                'asterion_remote.native_phone_relay:app','--host','127.0.0.1','--port','8995') `
                -WorkingDirectory $root -WindowStyle Hidden `
                -RedirectStandardOutput (Join-Path $state 'native-wss.stdout.log') `
                -RedirectStandardError (Join-Path $state 'native-wss.stderr.log')|Out-Null
              Add-Content (Join-Path $state 'control-watchdog-recovery.log') ('Native WSS handshake relay restart '+(Get-Date -Format o))
            }
          }
        }
      }
      $failures=0
    }
  }
  Set-Content -LiteralPath $nativeFailuresFile -Value ([string]$failures) -NoNewline -Encoding ASCII
}catch{
  # A failed health probe is not permission to reset credentials or the phone.
}

exit 0
