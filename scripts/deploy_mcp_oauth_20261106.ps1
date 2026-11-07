# Scoped MCP OAuth deployment; GitHub is only a source transport for this patch.
param([string]$Root='D:\AsterionControlRelease')
$ErrorActionPreference='Stop'
$gw=Join-Path $Root 'asterion_remote\mcp_gateway.py'
$oauth=Join-Path $Root 'asterion_remote\oauth_bridge.py'
$python=Join-Path $Root '.venv\Scripts\python.exe'
if(!(Test-Path $gw) -or !(Test-Path $python)){throw 'Existing gateway installation missing'}
$state=Join-Path $env:LOCALAPPDATA 'AsterionControl'
$backup=Join-Path $state ('oauth-backup-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Force -Path $backup | Out-Null
Copy-Item $gw (Join-Path $backup 'mcp_gateway.py')
if(Test-Path $oauth){Copy-Item $oauth (Join-Path $backup 'oauth_bridge.py')}
$uri='https://raw.githubusercontent.com/Azrazieliz/Asterion-Comander/work/android-primary-continuation-observation-20261105/asterion_remote/oauth_bridge.py'
$tmp=Join-Path $backup 'oauth_bridge.download.py'
Invoke-WebRequest -Uri $uri -UseBasicParsing -OutFile $tmp -TimeoutSec 25
if((Get-Item $tmp).Length -lt 10000 -or !(Select-String -Path $tmp -Pattern 'oauth-protected-resource' -Quiet)){throw 'Downloaded OAuth source invalid'}
Copy-Item $tmp $oauth -Force
$body=[IO.File]::ReadAllText($gw)
function Replace-Once([string]$old,[string]$new) {
  $count=([regex]::Matches($script:body,[regex]::Escape($old))).Count
  if($count -ne 1){throw "Gateway mismatch: expected one occurrence, got $count"}
  $script:body=$script:body.Replace($old,$new)
}
try {
  if(!$body.Contains('from .oauth_bridge import router as oauth_router')){
    $import="from .oauth_bridge import router as oauth_router, valid_access, challenge, SCOPE"+[Environment]::NewLine+"from .phone_bridge import load as load_phone"
    Replace-Once 'from .phone_bridge import load as load_phone' $import
    $include="app.include_router(phone_live_router)"+[Environment]::NewLine+"app.include_router(oauth_router)"
    Replace-Once 'app.include_router(phone_live_router)' $include
    $oldAuth=@'
    if not bearer.startswith("Bearer ") or not hmac.compare_digest(
        bearer[7:].encode(), _secret(GATEWAY_KEY).encode()
    ):
        raise HTTPException(
            401, "Asterion Control authorization required",
            headers={"WWW-Authenticate": "Bearer"},
        )
'@
    $newAuth=@'
    token = bearer[7:] if bearer.startswith("Bearer ") else ""
    if not token or not (
        hmac.compare_digest(token.encode(), _secret(GATEWAY_KEY).encode())
        or valid_access(token)
    ):
        raise HTTPException(
            401, "Asterion Control authorization required",
            headers={"WWW-Authenticate": challenge()},
        )
'@
    Replace-Once $oldAuth $newAuth
    $oldTools=@'
        response = {
            "jsonrpc": "2.0", "id": message.get("id"),
            "result": {"tools": list(merged.values())},
        }
'@
    $newTools=@'
        tools = []
        for spec in merged.values():
            tagged = dict(spec)
            tagged["_meta"] = {
                **(tagged.get("_meta") or {}),
                "securitySchemes": [{"type": "oauth2", "scopes": [SCOPE]}],
            }
            tools.append(tagged)
        response = {
            "jsonrpc": "2.0", "id": message.get("id"),
            "result": {"tools": tools},
        }
'@
    Replace-Once $oldTools $newTools
    [IO.File]::WriteAllText($gw,$body,(New-Object Text.UTF8Encoding($false)))
  }
  & $python -m py_compile $gw $oauth
  if($LASTEXITCODE -ne 0){throw 'Python compilation failed'}
  Push-Location $Root
  try {
    & $python -c 'from asterion_remote.mcp_gateway import app; from fastapi.testclient import TestClient; from pathlib import Path; import os; c=TestClient(app); assert c.get("/.well-known/oauth-protected-resource/mcp").status_code==200; assert c.get("/.well-known/oauth-authorization-server").status_code==200; h={"accept":"application/json, text/event-stream"}; assert c.post("/mcp",headers=h,json={"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}).status_code==401; k=(Path(os.environ["LOCALAPPDATA"])/"AsterionControl"/"mcp-gateway-token.txt").read_text().strip(); h["authorization"]="Bearer "+k; r=c.post("/mcp",headers=h,json={"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}); assert r.status_code==200 and r.json()["result"]["serverInfo"]["name"]=="asterion-control"; print("LOCAL_OAUTH_AND_BEARER_OK")'
    if($LASTEXITCODE -ne 0){throw 'Local regression checks failed'}
  } finally {Pop-Location}
} catch {
  Copy-Item (Join-Path $backup 'mcp_gateway.py') $gw -Force
  if(Test-Path (Join-Path $backup 'oauth_bridge.py')){Copy-Item (Join-Path $backup 'oauth_bridge.py') $oauth -Force}
  Write-Output ('SOURCE_ROLLED_BACK='+$backup)
  throw
}
$port=Get-NetTCPConnection -LocalPort 8995 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if($port){
  $owner=Get-CimInstance Win32_Process -Filter ("ProcessId="+$port.OwningProcess)
  if(!$owner -or $owner.CommandLine -notmatch 'asterion_remote\.mcp_gateway:app'){throw 'Unexpected process owns MCP port; not touching it'}
  Stop-Process -Id $port.OwningProcess -ErrorAction Stop
  Start-Sleep -Milliseconds 900
}
Start-Process -FilePath $python -WorkingDirectory $Root -ArgumentList @('-m','uvicorn','asterion_remote.mcp_gateway:app','--host','127.0.0.1','--port','8995') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $state 'mcp-oauth.stdout.log') -RedirectStandardError (Join-Path $state 'mcp-oauth.stderr.log') | Out-Null
$ready=$false
for($i=0;$i -lt 20;$i++){Start-Sleep -Milliseconds 450;try{$d=Invoke-RestMethod -Uri 'http://127.0.0.1:8995/.well-known/oauth-authorization-server' -TimeoutSec 2;if($d.issuer -eq 'https://wise-eagle-c8b55706.tunnl.gg'){$ready=$true;break}}catch{}}
if(!$ready){throw ('Local OAuth gateway restart failed, backup='+$backup)}
Write-Output 'GATEWAY_OAUTH_DEPLOYED=true'
try{
  $d=Invoke-RestMethod -Uri 'https://wise-eagle-c8b55706.tunnl.gg/.well-known/oauth-authorization-server' -TimeoutSec 12
  if($d.issuer -ne 'https://wise-eagle-c8b55706.tunnl.gg'){throw 'Wrong OAuth issuer'}
  Write-Output 'PUBLIC_OAUTH_DISCOVERY=true'
}catch{Write-Output ('PUBLIC_OAUTH_DISCOVERY=false '+$_.Exception.Message)}
Write-Output ('BACKUP='+$backup)
