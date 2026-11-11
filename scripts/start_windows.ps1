# Asterion Control Windows agent. Android is the primary interface.
# Private LAN/VPN Windows API. The native phone-outbound WSS is independent.
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root
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
# Control's source of truth for the current private endpoint.
$endpoint='http://'+$bind+':8911'
[System.IO.File]::WriteAllText(
  (Join-Path $settings 'agent-host.txt'),$endpoint,
  (New-Object System.Text.UTF8Encoding($false))
)
Write-Host ('Asterion Control Windows agent '+$endpoint)
$pinFile=Join-Path $settings 'pairing-code.txt'
# The separate private GitHub command/result worker is supervised by the
# existing Asterion watchdog. No MCP or SSH tunnel is launched here.
# Retired MCP/SSH ingress is intentionally disabled. The real Windows API
# and its existing authenticated Android transport require no public gateway.
# Restart the actual native agent after unexpected termination.
$failureCount=0
while($true){
  try {
    $listener=Get-NetTCPConnection -State Listen -LocalPort 8911 -ErrorAction SilentlyContinue |
      Select-Object -First 1
    if($listener){
      $owner=Get-CimInstance Win32_Process -Filter ("ProcessId="+$listener.OwningProcess) -ErrorAction Stop
      if(-not $owner -or $owner.CommandLine -notmatch 'uvicorn\s+asterion_remote\.app:app'){
        throw 'Port 8911 is owned by another process; refusing to interfere'
      }
      while(Get-Process -Id $owner.ProcessId -ErrorAction SilentlyContinue){
        Start-Sleep -Seconds 4
      }
    }else{
      Remove-Item $pinFile -ErrorAction SilentlyContinue
      $worker=Start-Process -FilePath $venv -ArgumentList @(
        '-m','uvicorn','asterion_remote.app:app','--host',$bind,'--port','8911'
      ) -NoNewWindow -PassThru
      if(-not $worker){throw 'Native Control agent failed to launch'}
      for($n=0;$n -lt 30;$n++){
        if($worker.HasExited){throw 'Native Control agent exited during startup'}
        if(Test-Path $pinFile){
          Write-Host ('ONE-TIME PAIRING CODE: '+(Get-Content $pinFile -Raw))
          break
        }
        Start-Sleep -Milliseconds 200
      }
      Wait-Process -Id $worker.Id
      Write-Warning ('Native Control agent stopped; restarting PID '+$worker.Id)
    }
    $failureCount=0
  }catch{
    $failureCount++
    Write-Warning ('Control recovery: '+$_.Exception.GetType().Name)
  }
  Start-Sleep -Seconds ([Math]::Min(30,3+($failureCount*3)))
}
