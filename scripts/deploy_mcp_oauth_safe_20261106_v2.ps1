# Apply only verified OAuth gateway files. No APK, no release, no GitHub runtime relay.
param([string]$Root='D:\AsterionControlRelease')
$ErrorActionPreference = 'Stop'
$py = Join-Path $Root '.venv\Scripts\python.exe'
$gateway = Join-Path $Root 'asterion_remote\mcp_gateway.py'
$oauth = Join-Path $Root 'asterion_remote\oauth_bridge.py'
$state = Join-Path $env:LOCALAPPDATA 'AsterionControl'
$backup = Join-Path $state ('oauth-safe-backup-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
if (!(Test-Path $py) -or !(Test-Path $gateway)){throw 'Expected installation missing'}
New-Item -ItemType Directory -Path $backup -Force | Out-Null
$originalGateway = Join-Path $backup 'mcp_gateway.original.py'
Copy-Item $gateway $originalGateway
if(Test-Path $oauth){Copy-Item $oauth (Join-Path $backup 'oauth_bridge.original.py')}
# Verify no unrelated local changes exist before replacing the running gateway source.
function Get-BlobHash([string]$path) {
  $raw=[IO.File]::ReadAllText($path)
  $raw=$raw.Replace(([string][char]13+[string][char]10),[string][char]10)
  if($raw.Length -gt 0 -and $raw[0] -eq [char]0xFEFF){$raw=$raw.Substring(1)}
  $bytes=[Text.Encoding]::UTF8.GetBytes($raw)
  $prefix=[Text.Encoding]::ASCII.GetBytes(("blob "+$bytes.Length+[char]0))
  $combined=New-Object byte[] ($prefix.Length+$bytes.Length)
  [Array]::Copy($prefix,0,$combined,0,$prefix.Length)
  [Array]::Copy($bytes,0,$combined,$prefix.Length,$bytes.Length)
  $digest=[Security.Cryptography.SHA1]::Create().ComputeHash($combined)
  return [BitConverter]::ToString($digest).Replace('-','').ToLowerInvariant()
}
$baseBlob = '6639ca9da2b425544328f6b6974d2644fae6ae01'
$updatedBlob = '23e811151f6af478a6278cc818d858ef9c831b48'
$currentBlob = Get-BlobHash $gateway
if($currentBlob -ne $baseBlob -and $currentBlob -ne $updatedBlob){throw ('Gateway has other changes; refusing overwrite (blob '+$currentBlob+')')}
$prefix='https://raw.githubusercontent.com/Azrazieliz/Asterion-Comander/b8832ab32e11b6a38596d7dd88408056196b11f6/asterion_remote/'
$stagedGateway=Join-Path $backup 'mcp_gateway.new.py'
$stagedOauth=Join-Path $backup 'oauth_bridge.new.py'
Invoke-WebRequest -Uri ($prefix+'mcp_gateway.py') -OutFile $stagedGateway -UseBasicParsing -TimeoutSec 25
Invoke-WebRequest -Uri ($prefix+'oauth_bridge.py') -OutFile $stagedOauth -UseBasicParsing -TimeoutSec 25
if((Get-Item $stagedGateway).Length -lt 12000 -or (Get-Item $stagedOauth).Length -lt 10000){throw 'Staged gateway source incomplete'}
$gatewayNewBlob=Get-BlobHash $stagedGateway
if($gatewayNewBlob -ne $updatedBlob){throw ('Staged gateway SHA mismatch: '+$gatewayNewBlob)}
$restarted=$false
try {
  Copy-Item $stagedGateway $gateway -Force
  Copy-Item $stagedOauth $oauth -Force
  & $py -m py_compile $gateway $oauth
  if($LASTEXITCODE -ne 0){throw 'OAuth gateway compilation failed'}
  Push-Location $Root
  try {
    # Verify OAuth discovery and both anonymous rejection and old bearer approval.
    & $py -c 'from asterion_remote.mcp_gateway import app; from fastapi.testclient import TestClient; from pathlib import Path; import os; c=TestClient(app); assert c.get("/.well-known/oauth-protected-resource/mcp").status_code==200; assert c.get("/.well-known/oauth-authorization-server").status_code==200; h={"accept":"application/json, text/event-stream"}; q={"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}; assert c.post("/mcp",headers=h,json=q).status_code==401; k=(Path(os.environ["LOCALAPPDATA"])/"AsterionControl"/"mcp-gateway-token.txt").read_text().strip(); h["authorization"]="Bearer "+k; r=c.post("/mcp",headers=h,json=q); assert r.status_code==200 and r.json()["result"]["serverInfo"]["name"]=="asterion-control"; print("PRE_RESTART_OAUTH_AND_LEGACY_BEARER_OK")'
    if($LASTEXITCODE -ne 0){throw 'Gateway OAuth/bearer checks failed'}
  } finally {Pop-Location}
  $port=Get-NetTCPConnection -LocalPort 8995 -State Listen -ErrorAction SilentlyContinue|Select-Object -First 1
  if($port){
    $owner=Get-CimInstance Win32_Process -Filter ("ProcessId="+$port.OwningProcess)
    if(!$owner -or $owner.CommandLine -notmatch 'asterion_remote\.mcp_gateway:app'){throw 'Unexpected process on gateway port'}
    Stop-Process -Id $port.OwningProcess -ErrorAction Stop
    Start-Sleep -Milliseconds 700
  }
  $logOut=Join-Path $state 'mcp-oauth.stdout.log'
  $logErr=Join-Path $state 'mcp-oauth.stderr.log'
  Start-Process -FilePath $py -ArgumentList @('-m','uvicorn','asterion_remote.mcp_gateway:app','--host','127.0.0.1','--port','8995') -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput $logOut -RedirectStandardError $logErr|Out-Null
  $restarted=$true
  $ready=$false
  for($i=0;$i -lt 22;$i++){
    Start-Sleep -Milliseconds 400
    try {$m=Invoke-RestMethod -Uri 'http://127.0.0.1:8995/.well-known/oauth-authorization-server' -TimeoutSec 2; if($m.issuer -eq 'https://wise-eagle-c8b55706.tunnl.gg'){$ready=$true;break}}catch{}
  }
  if(!$ready){throw 'OAuth gateway failed local discovery after restart'}
  Write-Output 'LOCAL_GATEWAY_OAUTH_DISCOVERY=true'
  try{
    $p=Invoke-RestMethod -Uri 'https://wise-eagle-c8b55706.tunnl.gg/.well-known/oauth-protected-resource/mcp' -TimeoutSec 10
    $m=Invoke-RestMethod -Uri 'https://wise-eagle-c8b55706.tunnl.gg/.well-known/oauth-authorization-server' -TimeoutSec 10
    if($p.resource -ne 'https://wise-eagle-c8b55706.tunnl.gg/mcp' -or $m.issuer -ne 'https://wise-eagle-c8b55706.tunnl.gg'){throw 'Unexpected metadata'}
    Write-Output 'PUBLIC_GATEWAY_OAUTH_DISCOVERY=true'
  }catch{Write-Output ('PUBLIC_GATEWAY_OAUTH_DISCOVERY=false '+$_.Exception.Message)}
} catch {
  Copy-Item $originalGateway $gateway -Force
  if(Test-Path (Join-Path $backup 'oauth_bridge.original.py')){Copy-Item (Join-Path $backup 'oauth_bridge.original.py') $oauth -Force}
  Write-Output ('OAUTH_DEPLOY_FAILED_BACKUP='+$backup)
  throw
}
Write-Output 'OAUTH_GATEWAY_SOURCE_DEPLOYED=true'
Write-Output ('BACKUP_PATH='+$backup)
