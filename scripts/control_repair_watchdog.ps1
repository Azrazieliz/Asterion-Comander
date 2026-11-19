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
# Monitor the private command relay independently of Windows API health.
# A live process is NOT proof it has fetched or acknowledged a command.
# This block must run BEFORE API failure branches that exit this watchdog.
$bridge=@(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
  Where-Object {$_.CommandLine -match '(?i)(^|\s)-m\s+asterion_remote\.github_bridge_git(\s|$)'})
# On Windows, a venv python.exe launcher can keep its real python.exe child
# alive under the SAME -m module invocation. That is ONE logical relay, not
# two independent workers. Only collapse a directly related, nearly
# simultaneous parent/child pair. Preserve the duplicate-worker guard for
# unrelated processes and for any other process topology.
if($bridge.Count -eq 2){
  $child=@($bridge | Where-Object {$bridge.ProcessId -contains $_.ParentProcessId})
  if($child.Count -eq 1){
    $parent=@($bridge | Where-Object {$_.ProcessId -eq $child[0].ParentProcessId})
    if($parent.Count -eq 1){
      $startGap=[math]::Abs(($child[0].CreationDate-$parent[0].CreationDate).TotalSeconds)
      if($startGap -le 5){
        # Prefer the executing child for safe idle-only restart: the waiting
        # venv launcher and existing supervisor will observe its termination.
        $bridge=@($child[0])
      }
    }
  }
}
$bridgeHealthFile=Join-Path $state 'control-git-bridge-health.json'
$bridgeRestartFile=Join-Path $state 'control-git-bridge-last-recovery.txt'
$bridgeLog=Join-Path $state 'control-watchdog-recovery.log'
$bridgeLauncher=Join-Path $PSScriptRoot 'start_git_bridge.ps1'
if($bridge.Count -eq 0){
  if(Test-Path $bridgeLauncher){
    # The existing launcher owns a mutex; never create a second relay.
    Start-Process powershell.exe -ArgumentList @('-NoProfile','-NonInteractive',
      '-ExecutionPolicy','Bypass','-File',('"'+$bridgeLauncher+'"')) `
      -WorkingDirectory $root -WindowStyle Hidden | Out-Null
    Add-Content $bridgeLog ('Git bridge missing; supervised launcher invoked '+(Get-Date -Format o))
  }
}elseif($bridge.Count -eq 1){
  $current=$bridge[0]
  $health=$null
  try {
    if(Test-Path $bridgeHealthFile){
      $health=Get-Content $bridgeHealthFile -Raw -ErrorAction Stop |
        ConvertFrom-Json -ErrorAction Stop
    }
  }catch{
    Add-Content $bridgeLog ('Git bridge heartbeat unreadable '+(Get-Date -Format o))
  }
  $ageSeconds=0.0
  if($health -and $health.heartbeat_utc){
    try{
      $ageSeconds=([datetimeoffset]::UtcNow -
        [datetimeoffset]::Parse([string]$health.heartbeat_utc)).TotalSeconds
    }catch{$ageSeconds=99999.0}
  }else{
    $ageSeconds=([datetimeoffset]::UtcNow -
      [datetimeoffset]$current.CreationDate.ToUniversalTime()).TotalSeconds
  }
  $syncAgeSeconds=0.0
  if($health -and $health.last_sync_utc){
    try{
      $syncAgeSeconds=([datetimeoffset]::UtcNow -
        [datetimeoffset]::Parse([string]$health.last_sync_utc)).TotalSeconds
    }catch{$syncAgeSeconds=99999.0}
  }elseif($ageSeconds -gt 0){$syncAgeSeconds=$ageSeconds}
  $errorCount=if($health){[int]$health.consecutive_errors}else{0}
  $stalled=($ageSeconds -ge 360 -or
    ($errorCount -ge 4 -and $syncAgeSeconds -ge 600))
  if($stalled){
    # Inflight operations may have already touched the phone or PC.
    # Never replay or terminate that worker without a durable receipt.
    $inflight=if($health){[string]$health.inflight_id}else{''}
    if(-not [string]::IsNullOrWhiteSpace($inflight)){
      Add-Content $bridgeLog ('Bridge stalled with uncertain in-flight action; NOT restarted '+(Get-Date -Format o))
    }else{
      # The Git relay and native Windows job host are separate processes.
      # Native jobs survive relay restart; accepted jobs reconcile via durable
      # receipts. Blocking on a full/unavailable native job list prevented
      # automatic recovery even when the relay had no in-flight operation.
      # The inflight_id safety guard above is unchanged.
      $cooldown=$true
      $cooldownReason='none'
      if(Test-Path $bridgeRestartFile){
        try {
          $last=[datetimeoffset]::Parse((Get-Content $bridgeRestartFile -Raw).Trim())
          $cooldown=(([datetimeoffset]::UtcNow-$last).TotalMinutes -ge 10)
          if(-not $cooldown){$cooldownReason='recent_recovery'}
        }catch{
          $cooldown=$false
          $cooldownReason='unreadable_last_recovery'
        }
      }
      if($cooldown){
        # Only the uniquely identified stale Git relay is terminated.
        # The existing supervisor restarts it; no native jobs are terminated.
        try {
          Stop-Process -Id $current.ProcessId -Force -ErrorAction Stop
          Set-Content -LiteralPath $bridgeRestartFile -Value (Get-Date -Format o) -Encoding ASCII
          Add-Content $bridgeLog ('Stalled private Git bridge PID '+$current.ProcessId+
            ' restarted by existing supervisor '+(Get-Date -Format o))
        }catch{
          Add-Content $bridgeLog ('Stalled Git bridge restart failed '+(Get-Date -Format o))
        }
      }else{
        Add-Content $bridgeLog ('Stalled Git bridge restart deferred cooldown='+
          $cooldown+' cooldownReason='+$cooldownReason+' '+(Get-Date -Format o))
      }
    }
  }
}elseif($bridge.Count -gt 1){
  # Two relays would risk duplicate phone actions. Do not kill blindly.
  Add-Content $bridgeLog ('Multiple Git relay workers detected; manual inspection required '+(Get-Date -Format o))
}

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
# Private Git bridge liveness is checked above, before native API recovery exits.

# R01: a native relay may report connected while its running process
# predates its installed RPC route (HTTP 404 despite /healthz healthy).
# Use only the owner's guarded reload, not another gateway or pairing.
if($nativeRelayOk){
  $rpcStatus=0
  try{
    $rpcProbe=Invoke-WebRequest 'http://127.0.0.1:8995/phone/rpc' -Method Get -UseBasicParsing -TimeoutSec 2
    $rpcStatus=[int]$rpcProbe.StatusCode
  }catch{
    if($_.Exception.Response){$rpcStatus=[int]$_.Exception.Response.StatusCode}
  }
  if($rpcStatus -eq 404){
    $reload=Join-Path $PSScriptRoot 'reload_native_wss_after_idle_20261119.ps1'
    $attempt=Join-Path $state 'v6-native-route-recovery-attempt.txt'
    $cooldown=$true
    if(Test-Path $attempt){
      try{
        $last=[datetimeoffset]::Parse((Get-Content -LiteralPath $attempt -Raw).Trim())
        $cooldown=(([datetimeoffset]::UtcNow-$last).TotalMinutes -ge 10)
      }catch{$cooldown=$false}
    }
    $already=@(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {$_.Name -match '^powershell(?:\.exe)?
# Only intervene after two real phone-side handshake rejections while the phone
# remains reachable. Never alter Android permissions, keys, pairing or other services.
$nativeFailuresFile=Join-Path $state 'native-wss-handshake-failures.txt'
$nativeLastRestartFile=Join-Path $state 'native-wss-last-restart.txt'
try{
  $phone=Invoke-RestMethod ($url+'/api/v1/phone') -Headers @{Authorization=('Bearer '+$token)} -TimeoutSec 3
  $direct=$phone.info.remote_transport.direct_mcp
  $rejected=[bool]($nativeRelayOk -and $phone.reachable -and $direct -and
    -not $direct.connected -and $direct.last_stage -eq 'wss_upgrade' -and
    $direct.last_error_detail -match 'WSS handshake rejected|WSS upgrade HTTP (400|403|502)')
  $failures=0
  if($rejected){
    if(Test-Path $nativeFailuresFile){
      [void][int]::TryParse((Get-Content $nativeFailuresFile -Raw).Trim(),[ref]$failures)
    }
    $failures=[math]::Min(99,$failures+1)
    $lastRestart=[datetime]::MinValue
    if(Test-Path $nativeLastRestartFile){
      [void][datetime]::TryParse((Get-Content $nativeLastRestartFile -Raw).Trim(),[ref]$lastRestart)
    }
    $cooldownOk=((Get-Date)-$lastRestart).TotalMinutes -ge 10
    if($failures -ge 2 -and $cooldownOk){
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
              Set-Content -LiteralPath $nativeLastRestartFile -Value (Get-Date -Format o) -Encoding ASCII
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
 -and $_.CommandLine -match 'reload_native_wss_after_idle_20261119\.ps1'})
    if($cooldown -and $already.Count -eq 0 -and (Test-Path -LiteralPath $reload)){
      Set-Content -LiteralPath $attempt -Value (Get-Date -Format o) -Encoding ASCII
      Start-Process powershell.exe -ArgumentList @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',('"'+$reload+'"'),'-Apply') -WorkingDirectory $root -WindowStyle Hidden | Out-Null
      Add-Content $bridgeLog ('Native RPC route 404; owner-relay guarded reload invoked '+(Get-Date -Format o))
    }
  }
}

# Native WSS recovery: a running process alone is not proof of a usable phone link.
# Only intervene after two real phone-side handshake rejections while the phone
# remains reachable. Never alter Android permissions, keys, pairing or other services.
$nativeFailuresFile=Join-Path $state 'native-wss-handshake-failures.txt'
$nativeLastRestartFile=Join-Path $state 'native-wss-last-restart.txt'
try{
  $phone=Invoke-RestMethod ($url+'/api/v1/phone') -Headers @{Authorization=('Bearer '+$token)} -TimeoutSec 3
  $direct=$phone.info.remote_transport.direct_mcp
  $rejected=[bool]($nativeRelayOk -and $phone.reachable -and $direct -and
    -not $direct.connected -and $direct.last_stage -eq 'wss_upgrade' -and
    $direct.last_error_detail -match 'WSS handshake rejected|WSS upgrade HTTP (400|403|502)')
  $failures=0
  if($rejected){
    if(Test-Path $nativeFailuresFile){
      [void][int]::TryParse((Get-Content $nativeFailuresFile -Raw).Trim(),[ref]$failures)
    }
    $failures=[math]::Min(99,$failures+1)
    $lastRestart=[datetime]::MinValue
    if(Test-Path $nativeLastRestartFile){
      [void][datetime]::TryParse((Get-Content $nativeLastRestartFile -Raw).Trim(),[ref]$lastRestart)
    }
    $cooldownOk=((Get-Date)-$lastRestart).TotalMinutes -ge 10
    if($failures -ge 2 -and $cooldownOk){
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
              Set-Content -LiteralPath $nativeLastRestartFile -Value (Get-Date -Format o) -Encoding ASCII
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
