# Restart only the Asterion Control agent after source deployment.
# The scheduled child process survives a disconnected ChatGPT client.
$ErrorActionPreference = 'Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Start-Sleep -Seconds 2
$listener=Get-NetTCPConnection -State Listen -LocalPort 8911 -ErrorAction SilentlyContinue | Select-Object -First 1
if($listener){
  $proc=Get-CimInstance Win32_Process -Filter ("ProcessId="+$listener.OwningProcess)
  if($proc.CommandLine -notmatch 'uvicorn\s+asterion_remote\.app:app'){
    throw 'Refusing to stop a non-Control process bound to 8911'
  }
  Stop-Process -Id $listener.OwningProcess -Force
  Start-Sleep -Milliseconds 450
}
$out=Join-Path $root 'WINDOWS_AGENT_STDOUT.log'
$err=Join-Path $root 'WINDOWS_AGENT_STDERR.log'
$launcher=(Resolve-Path (Join-Path $PSScriptRoot 'start_windows.ps1')).Path
$child=Start-Process powershell.exe -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',('"'+$launcher+'"') -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
Write-Host ('Asterion Control agent restart PID '+$child.Id)
