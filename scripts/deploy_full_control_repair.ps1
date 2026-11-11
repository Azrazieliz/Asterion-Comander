# Safely admit only the reviewed recovery files into the actual running Control worker.
# Preserves every existing modified Windows file, token, pairing, screen permission and build.
$ErrorActionPreference='Stop'
$source=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$live='D:\AsterionControlRelease'
if(-not(Test-Path (Join-Path $live '.venv\Scripts\python.exe'))){throw 'Existing Windows Control worker installation missing'}
$state=Join-Path $env:LOCALAPPDATA 'AsterionControl'
if(-not(Test-Path (Join-Path $state 'control-token.txt'))){throw 'Existing pairing missing: refusing any installation'}
$python=Join-Path $live '.venv\Scripts\python.exe'
$parts=@(
  'asterion_remote\recovery.py',
  'scripts\control_full_repair.ps1',
  'scripts\control_repair_watchdog.ps1',
  'scripts\install_control_repair_watchdog.ps1'
)
foreach($part in $parts){
  $origin=Join-Path $source $part
  if(-not(Test-Path $origin)){throw ('Missing reviewed component: '+$part)}
}
$parser=[System.Management.Automation.Language.Parser]
foreach($part in @($parts|Where-Object {$_ -like '*.ps1'})){
  $t=$null;$errors=$null;[void]$parser::ParseFile((Join-Path $source $part),[ref]$t,[ref]$errors)
  if($errors.Count -gt 0){throw ('Unsafe PowerShell source syntax: '+$part)}
}
& $python -m py_compile (Join-Path $source 'asterion_remote\recovery.py')
if($LASTEXITCODE -ne 0){throw 'Recovery Python syntax invalid'}
$backup=Join-Path $state 'recovery-source-backup-20261111'
New-Item -ItemType Directory $backup -Force|Out-Null
$app=Join-Path $live 'asterion_remote\app.py'
$appOld=[System.IO.File]::ReadAllText($app)
if(-not $appOld.Contains('from .native_routes import router as phone_router') -or
   -not $appOld.Contains('app.include_router(phone_router)')){
  throw 'Running Windows worker API differs from expected; no changes made'
}
$appNew=$appOld
if(-not $appNew.Contains('from .recovery import router as recovery_router')){
  $appNew=$appNew.Replace('from .native_routes import router as phone_router',
    'from .native_routes import router as phone_router'+"\n"+'from .recovery import router as recovery_router')
}
if(-not $appNew.Contains('app.include_router(recovery_router)')){
  $appNew=$appNew.Replace('app.include_router(phone_router)',
    'app.include_router(phone_router)'+"\n"+'app.include_router(recovery_router)')
}
Copy-Item -LiteralPath $app -Destination (Join-Path $backup 'app.py.original') -Force
foreach($part in $parts){
  $origin=Join-Path $source $part
  $dest=Join-Path $live $part
  if(Test-Path $dest){Copy-Item -LiteralPath $dest -Destination (Join-Path $backup ([IO.Path]::GetFileName($part)+'.previous')) -Force}
  Copy-Item -LiteralPath $origin -Destination $dest -Force
}
try{
  if($appNew -ne $appOld){
    [IO.File]::WriteAllText($app,$appNew,(New-Object System.Text.UTF8Encoding($false)))
  }
  & $python -m py_compile $app (Join-Path $live 'asterion_remote\recovery.py')
  if($LASTEXITCODE -ne 0){throw 'Windows worker API import or recovery syntax invalid'}
}catch{
  Copy-Item (Join-Path $backup 'app.py.original') $app -Force
  throw
}
$watchdog=(Join-Path $live 'scripts\install_control_repair_watchdog.ps1')
& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $watchdog
if($LASTEXITCODE -ne 0){throw 'Recovery files staged; Windows scheduled watchdog registration failed'}
Write-Output 'CONTROL_RECOVERY_INSTALLED_ON_ACTIVE_WORKER=true'
Write-Output 'CURRENT_RUNNING_WORKER_UNCHANGED_UNTIL_SAFE_RESTART=true'
Write-Output 'PAIRING_CREDENTIALS_PRESERVED=true'
Write-Output 'MANAGED_BACKUP_CREATED=true'
