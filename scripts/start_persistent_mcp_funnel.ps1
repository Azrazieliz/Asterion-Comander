# Persistent authenticated MCP endpoint, using the owner's existing Control gateway.
# One-time Tailscale login/consent is required; no secrets enter GitHub.
# This does not install APKs, modify mobile-data settings, or start any AI.
param([switch]$Maintain,[switch]$InstallIfMissing)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$state=Join-Path $env:LOCALAPPDATA 'AsterionControl'
New-Item -ItemType Directory $state -Force | Out-Null
$python=Join-Path $root '.venv\Scripts\python.exe'
if(-not(Test-Path $python)){throw 'Control Python environment is missing'}
$tokenFile=Join-Path $state 'mcp-gateway-token.txt'
if(-not(Test-Path $tokenFile)){
  $secret=(& $python -c 'import secrets;print(secrets.token_urlsafe(48))')
  if($LASTEXITCODE -ne 0 -or $secret.Length -lt 43){throw 'MCP bearer token generation failed'}
  Set-Content -Path $tokenFile -Value $secret -NoNewline -Encoding ASCII
  $acl=Get-Acl $tokenFile
  $acl.SetAccessRuleProtection($true,$false)
  $owner=[System.Security.Principal.WindowsIdentity]::GetCurrent().Name
  $rule=New-Object System.Security.AccessControl.FileSystemAccessRule($owner,'FullControl','Allow')
  $acl.SetAccessRule($rule)
  Set-Acl $tokenFile $acl
}
$token=(Get-Content $tokenFile -Raw).Trim()
if($token.Length -lt 43){throw 'Invalid existing MCP bearer token'}
$tCmd=Get-Command tailscale.exe -ErrorAction SilentlyContinue
$tExe=if($tCmd){$tCmd.Source}else{'C:\Program Files\Tailscale\tailscale.exe'}
if(-not(Test-Path $tExe)){
  if($InstallIfMissing){
    $winget=Get-Command winget.exe -ErrorAction SilentlyContinue
    if(-not $winget){throw 'TAILSCALE_INSTALL_REQUIRED: no winget. Install official Tailscale for Windows'}
    & $winget.Source install --id Tailscale.Tailscale --exact --silent --accept-package-agreements --accept-source-agreements
    if($LASTEXITCODE -ne 0){throw 'TAILSCALE_INSTALL_REQUIRES_OWNER_APPROVAL'}
  }
  $tExe='C:\Program Files\Tailscale\tailscale.exe'
  if(-not(Test-Path $tExe)){throw 'TAILSCALE_INSTALL_REQUIRED'}
}
$tailJson=(& $tExe status --json 2>$null | Out-String)
if($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($tailJson)){
  throw 'TAILSCALE_SIGN_IN_REQUIRED: use the owners Tailscale account'
}
$tail=$tailJson | ConvertFrom-Json
if($tail.BackendState -ne 'Running' -or -not $tail.Self){
  throw 'TAILSCALE_SIGN_IN_REQUIRED: Tailscale must be connected'
}
$fqdn=([string]$tail.Self.DNSName).TrimEnd('.').ToLowerInvariant()
if($fqdn -notmatch '^[a-z0-9-]+(\.[a-z0-9-]+)+\.ts\.net$'){
  throw 'TAILSCALE_DNS_REQUIRED: enable MagicDNS and HTTPS on the tailnet'
}
$local='http://127.0.0.1:8995/mcp'
$headers=@{Authorization=('Bearer '+$token);Accept='application/json, text/event-stream'}
$body=@{jsonrpc='2.0';id=1;method='initialize';params=@{protocolVersion='2025-11-25';capabilities=@{};clientInfo=@{name='asterion-persistent-probe';version='1.0'}}} | ConvertTo-Json -Compress -Depth 7
$ready=$false
try{
  $initialized=Invoke-RestMethod -Uri $local -Method Post -Headers $headers -ContentType 'application/json' -Body $body -TimeoutSec 4
  $ready=$initialized.result.serverInfo.name -eq 'asterion-control'
}catch{}
if(-not $ready){
  $listener=Get-NetTCPConnection -State Listen -LocalPort 8995 -ErrorAction SilentlyContinue | Select-Object -First 1
  if($listener){throw 'Port 8995 belongs to another service or an unauthenticated gateway'}
  $out=Join-Path $state 'mcp-persistent.stdout.log'
  $err=Join-Path $state 'mcp-persistent.stderr.log'
  $worker=Start-Process -FilePath $python -ArgumentList @(
    '-m','uvicorn','asterion_remote.mcp_gateway:app','--host','127.0.0.1','--port','8995'
  ) -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput $out -RedirectStandardError $err
  for($i=0;$i -lt 16;$i++){
    Start-Sleep -Milliseconds 500
    if($worker.HasExited){throw 'MCP gateway failed to start'}
    try{
      $initialized=Invoke-RestMethod -Uri $local -Method Post -Headers $headers -ContentType 'application/json' -Body $body -TimeoutSec 2
      if($initialized.result.serverInfo.name -eq 'asterion-control'){$ready=$true;break}
    }catch{}
  }
  if(-not $ready){throw 'MCP gateway local authentication failed'}
}
# The native phone/Windows Control HTTP port is not exposed, only the MCP gateway.
# An unauthenticated POST must fail before we enable any public HTTPS route.
try{
  $unused=Invoke-WebRequest -Uri $local -Method Post -ContentType 'application/json' -Body '{}' -TimeoutSec 5
  throw 'SECURITY: MCP gateway accepted an unauthenticated request'
}catch [System.Net.WebException]{
  if([int]$_.Exception.Response.StatusCode -ne 401){throw 'MCP gateway has unexpected unauthenticated response'}
}
if(-not $Maintain){
  $funnelJson=(& $tExe funnel status --json 2>$null | Out-String)
  if($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($funnelJson)){
    try{
      $previous=$funnelJson | ConvertFrom-Json
      if($previous.Web -and @($previous.Web.PSObject.Properties).Count -gt 0 -and
         $funnelJson -notmatch '127\.0\.0\.1:8995'){
        throw 'Existing Funnel routes to another service; refusing to overwrite'
      }
    }catch [System.ArgumentException]{throw 'Cannot safely inspect existing Funnel configuration'}
  }
  & $tExe funnel --bg --yes --https=443 http://127.0.0.1:8995
  if($LASTEXITCODE -ne 0){throw 'TAILSCALE_FUNNEL_PERMISSION_REQUIRED: owner must approve Funnel once'}
  Set-Content (Join-Path $state 'mcp-persistent-enabled.flag') -Value '1' -Encoding ASCII
}
$url='https://'+$fqdn+'/mcp'
try{
  $online=Invoke-RestMethod -Uri $url -Method Post -Headers $headers -ContentType 'application/json' -Body $body -TimeoutSec 18
  if($online.result.serverInfo.name -ne 'asterion-control'){throw 'Wrong public MCP server identity'}
  try{
    $unused=Invoke-WebRequest -Uri $url -Method Post -ContentType 'application/json' -Body '{}' -TimeoutSec 12
    throw 'SECURITY: public endpoint accepted an unauthenticated request'
  }catch [System.Net.WebException]{
    if([int]$_.Exception.Response.StatusCode -ne 401){throw 'Public endpoint did not reject an anonymous call'}
  }
  Set-Content (Join-Path $state 'mcp-persistent-url.txt') -Value $url -Encoding ASCII
  Write-Output ('CONTROL_PERSISTENT_MCP_VERIFIED='+$url)
  Write-Output 'CONTROL_PUBLIC_AUTHENTICATION_VERIFIED=true'
}catch{
  Write-Output ('CONTROL_PERSISTENT_MCP_CONFIGURED_NOT_VERIFIED='+$url)
  throw
}
