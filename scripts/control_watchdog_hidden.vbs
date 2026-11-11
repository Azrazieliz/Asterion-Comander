Option Explicit
' Invisible launcher for the existing owner-authorized one-minute recovery watchdog.
' No shell window is allocated, and credentials remain in the existing worker state.
Dim sh, fso, root, task, command
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
task = fso.BuildPath(root, "control_repair_watchdog.ps1")
command = "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & task & """"
sh.Run command, 0, True
