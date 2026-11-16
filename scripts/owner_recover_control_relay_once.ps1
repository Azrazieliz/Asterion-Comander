# Owner-local emergency Asterion Control repair, safe when remote relay is offline.
# Runs exclusively on the original Windows PC. No pairing/key/data reset.
$ErrorActionPreference='Stop'
$production='D:\AsterionControlRelease'
$branch='work/control-0927-overnight-cycles-20261111'
if(-not(Test-Path (Join-Path $production 'asterion_remote\github_bridge_git.py'))){
 throw 'Original Control installation missing; refusing another installation'
}
$python=Join-Path $production '.venv\Scripts\python.exe'
if(-not(Test-Path $python)){throw 'Existing Control Python environment unavailable'}
$source=Join-Path $env:TEMP 'asterion-control-triage-mwid4xob'
if(-not(Test-Path (Join-Path $source '.git'))){
 $source=Join-Path $env:LOCALAPPDATA 'AsterionControl\bridge-repair-source'
 if(Test-Path $source){
   throw 'Recovery checkout exists but is not a Git checkout; left untouched'
 }
 & git clone --depth 1 --single-branch --branch $branch 'https://github.com/Azrazieliz/Asterion-Comander.git' $source
 if($LASTEXITCODE -ne 0){throw 'Could not retrieve authenticated Control recovery source'}
}
$origin=(& git -C $source remote get-url origin).Trim().ToLowerInvariant().TrimEnd('/')
if($origin -notin @(
 'https://github.com/azrazieliz/asterion-comander.git',
 'https://github.com/azrazieliz/asterion-comander',
 'git@github.com:azrazieliz/asterion-comander.git'
)){throw 'Unexpected source remote; no changes made'}
$current=(& git -C $source branch --show-current).Trim()
if($current -ne $branch){throw 'Unexpected source branch; no changes made'}
$dirty=@(& git -C $source status --porcelain --untracked-files=no)
if(($dirty -join '').Trim()){throw 'Local tracked changes detected; no changes made'}
& git -C $source pull --ff-only origin $branch
if($LASTEXITCODE -ne 0){throw 'Could not update recovery source safely'}
$deploy=Join-Path $source 'scripts\deploy_private_bridge_recovery_20261116.py'
if(-not(Test-Path $deploy)){throw 'Recovery deployment script unavailable'}
& $python $deploy --apply
if($LASTEXITCODE -ne 0){throw 'Guarded source deployment failed; see immutable backup receipts'}
# The original minute watchdog validates idle native jobs before recovering
# the uniquely identified stalled private Git process.
$task='Asterion Control Self-Healing Worker'
& schtasks.exe /Query /TN $task *> $null
if($LASTEXITCODE -ne 0){
 throw 'Source updated; original watchdog task unavailable. No process was killed.'
}
& schtasks.exe /Run /TN $task *> $null
if($LASTEXITCODE -ne 0){
 throw 'Source updated; existing watchdog could not be started. No process was killed.'
}
Write-Output 'OWNER_CONTROL_RELAY_RECOVERY_INSTALLED; original task invoked; pairing unchanged'
Write-Output 'Check private bridge heartbeat and GitHub receipt before claiming operational recovery'
