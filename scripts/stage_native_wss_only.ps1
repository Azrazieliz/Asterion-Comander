# Stage reviewed native-WSS-only components over the existing Windows worker.
# This step does not restart services, change the tunnel, or delete credentials.
$ErrorActionPreference='Stop'
$source=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$live='D:\AsterionControlRelease'
$state=Join-Path $env:LOCALAPPDATA 'AsterionControl'
$python=Join-Path $live '.venv\Scripts\python.exe'
if(-not(Test-Path $python) -or -not(Test-Path (Join-Path $state 'control-token.txt'))){
  throw 'Existing authorized Windows worker/pairing unavailable; no changes made'
}
$parts=@(
  'asterion_remote\native_phone_live.py',
  'asterion_remote\native_phone_relay.py',
  'scripts\control_repair_watchdog.ps1',
  'scripts\start_windows.ps1',
  'scripts\start_native_wss_tunnel.py'
)
foreach($part in $parts){
  if(-not(Test-Path (Join-Path $source $part))){throw ('Source file missing: '+$part)}
}
foreach($part in @('scripts\control_repair_watchdog.ps1','scripts\start_windows.ps1')){
  $tokens=$null;$parseErrors=$null
  [void][System.Management.Automation.Language.Parser]::ParseFile(
    (Join-Path $source $part),[ref]$tokens,[ref]$parseErrors)
  if(@($parseErrors).Count -gt 0){throw ('PowerShell source invalid: '+$part)}
}
$backup=Join-Path $state ('backups\native-wss-only-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backup -Force|Out-Null
$app=Join-Path $live 'asterion_remote\app.py'
$appOld=[IO.File]::ReadAllText($app)
$replace=@(
  "from .mcp_setup import router as mcp_setup_router",
  "app.include_router(mcp_setup_router)",
  "# Register MCP /mcp endpoint in the same REST server.",
  "from . import mcp_protocol  # noqa: E402,F401"
)
$appNew=$appOld
foreach($obsolete in $replace){
  if($appNew.Contains($obsolete)){
    $appNew=$appNew.Replace($obsolete,'')
  }elseif($obsolete -like '*mcp_setup*' -and
     ($appNew.Contains('mcp_setup_router'))){
    throw 'Unrecognized legacy gateway router source'
  }
}
if($appNew.Contains('mcp_setup_router') -or
   $appNew.Contains('from . import mcp_protocol')){
  throw 'Unrecognized legacy HTTP MCP registration; refusing partial edit'
}
if(-not $appNew.Contains('app.include_router(phone_router)') -or
   -not $appNew.Contains('install_stream(app,')){
  throw 'Native Windows phone/desktop routing unexpectedly absent'
}
Copy-Item $app (Join-Path $backup 'app.py.original') -Force
foreach($part in $parts){
  $target=Join-Path $live $part
  $old=Join-Path $backup (($part -replace '[\\/]','_')+'.previous')
  if(Test-Path $target){Copy-Item $target $old -Force}
  $parent=Split-Path $target -Parent
  if(-not(Test-Path $parent)){New-Item -ItemType Directory -Path $parent -Force|Out-Null}
  Copy-Item (Join-Path $source $part) $target -Force
}
[IO.File]::WriteAllText($app,$appNew,(New-Object Text.UTF8Encoding($false)))
& $python -m py_compile $app (Join-Path $live 'asterion_remote\native_phone_live.py') `
  (Join-Path $live 'asterion_remote\native_phone_relay.py') `
  (Join-Path $live 'scripts\start_native_wss_tunnel.py')
if($LASTEXITCODE -ne 0){
  Copy-Item (Join-Path $backup 'app.py.original') $app -Force
  throw 'Native-only Windows source validation failed; restored Windows API'
}
Write-Output 'NATIVE_ONLY_SOURCE_STAGED=true'
Write-Output 'EXISTING_WORKER_UNCHANGED_UNTIL_SAFE_RESTART=true'
Write-Output 'PAIRING_AND_SSH_IDENTITY_PRESERVED=true'
Write-Output ('BACKUP='+$backup)
