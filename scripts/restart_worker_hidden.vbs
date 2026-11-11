Option Explicit
' Detached invisible safe reload: waits for the current API job to exit.
Dim sh, fso, root, task, command
Set sh=CreateObject("WScript.Shell")
Set fso=CreateObject("Scripting.FileSystemObject")
root=fso.GetParentFolderName(WScript.ScriptFullName)
task=fso.BuildPath(root,"restart_control_after_idle.ps1")
command="powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & task & """"
sh.Run command, 0, False
