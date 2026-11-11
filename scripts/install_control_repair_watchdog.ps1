# Install/repair the original minute watchdog WITHOUT displaying a PowerShell window.
# The scheduled task runs wscript.exe, not a console-hosted powershell.exe.
# No worker restart, credential reset, desktop control or installer invocation.
$ErrorActionPreference='Stop'
$launcher=(Resolve-Path (Join-Path $PSScriptRoot 'control_watchdog_hidden.vbs')).Path
$task='Asterion Control Self-Healing Worker'
$cmd='wscript.exe //B //Nologo "'+$launcher+'"'
& schtasks.exe /Create /F /SC MINUTE /MO 1 /TN $task /TR $cmd | Out-Null
if($LASTEXITCODE -ne 0){throw 'Could not install hidden Windows watchdog'}
$observed=Get-ScheduledTask -TaskName $task -ErrorAction Stop
$action=@($observed.Actions)[0]
if($action.Execute -notmatch '(?i)wscript(?:\.exe)?$' -or
   $action.Arguments -notmatch 'control_watchdog_hidden\.vbs'){
   throw 'Task registration did not replace the console launcher'
}
& schtasks.exe /Run /TN $task | Out-Null
if($LASTEXITCODE -ne 0){throw 'Watchdog registered but test launch failed'}
Write-Output 'ASTERION_HIDDEN_WATCHDOG_INSTALLED_AND_INVOKED'
