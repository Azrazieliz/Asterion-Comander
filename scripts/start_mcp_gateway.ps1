# Asterion Control direct MCP trial: Windows is an HTTPS transport for the authorized Android principal.
# No GitHub transport needed after the ChatGPT MCP connection is configured.
# Credentials remain under %LOCALAPPDATA%\AsterionControl; never commit them.
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root
$state=Join-Path $env:LOCALAPPDATA 'AsterionControl'
New-Item -ItemType Directory $state -Force | Out-Null
$key=Join-Path $state 'mcp-gateway-token.txt'
$py=Join-Path $root '.venv\Scripts\python.exe'
if(-not(Test-Path $py)){throw 'Asterion Python venv missing'}
if(-not(Test-Path $key)){
  $created=(& $py -c 'import secrets; print(secrets.token_urlsafe(48))')
  if($LASTEXITCODE -ne 0 -or $created.Length -lt 43){throw 'Could not generate MCP secret'}
  Set-Content $key $created -NoNewline -Encoding ASCII
  $acl=Get-Acl $key
  $acl.SetAccessRuleProtection($true,$false)
  $user=[System.Security.Principal.WindowsIdentity]::GetCurrent().Name
  $rule=New-Object System.Security.AccessControl.FileSystemAccessRule($user,'FullControl','Allow')
  $acl.SetAccessRule($rule)
  Set-Acl $key $acl
}
$gatewayLog=Join-Path $state 'mcp-gateway.stdout.log'
$gatewayErrors=Join-Path $state 'mcp-gateway.stderr.log'
# Separate process / remote gateway only, no regular app UI or REST routes exposed through tunnel.
$probe=Test-NetConnection -ComputerName 127.0.0.1 -Port 8995 -WarningAction SilentlyContinue
if(-not $probe.TcpTestSucceeded){
  $process=Start-Process $py -ArgumentList '-m','uvicorn','asterion_remote.mcp_gateway:app','--host','127.0.0.1','--port','8995' -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput $gatewayLog -RedirectStandardError $gatewayErrors
  Start-Sleep -Seconds 2
  if($process.HasExited){throw ('MCP gateway failed: '+((Get-Content $gatewayErrors -Tail 10)-join ';'))}
}
$initial=@{jsonrpc='2.0';id=1;method='initialize';params=@{protocolVersion='2025-11-25';capabilities=@{};clientInfo=@{name='asterion-control-bootstrap';version='1'}}} | ConvertTo-Json -Depth 8 -Compress
$headers=@{Authorization=('Bearer '+(Get-Content $key -Raw).Trim());Accept='application/json, text/event-stream'}
$answer=Invoke-RestMethod -Uri 'http://127.0.0.1:8995/mcp' -Method Post -Body $initial -ContentType 'application/json' -Headers $headers -TimeoutSec 12
if($answer.result.serverInfo.name -ne 'asterion-control'){throw 'MCP loopback did not initialize'}
Write-Output 'MCP_AUTHENTICATED_LOOPBACK_OK'
$cloudflared=Join-Path $state 'cloudflared.exe'
if(-not(Test-Path $cloudflared)){
  $download='https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe'
  Invoke-WebRequest -Uri $download -OutFile ($cloudflared+'.part') -UseBasicParsing -TimeoutSec 90
  if((Get-Item ($cloudflared+'.part')).Length -lt 1000000){throw 'cloudflared download too small'}
  Move-Item ($cloudflared+'.part') $cloudflared -Force
}
$tunnelLog=Join-Path $state 'cloudflared.stdout.log'
$tunnelErrors=Join-Path $state 'cloudflared.stderr.log'
$tunnelProc=Start-Process $cloudflared -ArgumentList 'tunnel','--no-autoupdate','--protocol','http2','--url','http://127.0.0.1:8995' -WorkingDirectory $state -WindowStyle Hidden -PassThru -RedirectStandardOutput $tunnelLog -RedirectStandardError $tunnelErrors
$public=$null
for($i=0;$i -lt 25;$i++){
  Start-Sleep -Milliseconds 900
  if($tunnelProc.HasExited){throw 'Cloudflare outbound tunnel exited: '+((Get-Content $tunnelErrors -Tail 8)-join ';')}
  $log=(Get-Content $tunnelErrors -Raw -ErrorAction SilentlyContinue)
  if($log -match 'https://[a-zA-Z0-9-]+\.trycloudflare\.com'){$public=$Matches[0];break}
}
if(-not $public){throw 'No HTTPS tunnel URL returned: '+((Get-Content $tunnelErrors -Tail 8)-join ';')}
Set-Content (Join-Path $state 'mcp-tunnel-url.txt') $public -Encoding ASCII
Write-Output ('MCP_TUNNEL_URL='+$public+'/mcp')
Write-Output ('MCP_TUNNEL_PID='+$tunnelProc.Id)
Write-Output 'MCP_GATEWAY_TOKEN_REMAINS_PRIVATE'
