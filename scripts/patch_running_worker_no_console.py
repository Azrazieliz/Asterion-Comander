"""Patch ONLY Windows CREATE_NO_WINDOW flags on the already-running worker source.
Preserve all live local modifications, credentials and runtime state.
Restart separately only after the current tracked job has finished.
"""
import ast
import os
import shutil
import time
from pathlib import Path

root=Path(r"D:\AsterionControlRelease")
target=root/"asterion_remote"/"app.py"
source=target.read_text(encoding="utf-8")
needle=[
("cp = subprocess.run(args, capture_output=True, timeout=timeout, check=False)",
 "cp = subprocess.run(args, capture_output=True, timeout=timeout, check=False,\n                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))",1),
("subprocess.run(['taskkill', '/PID', str(row['proc'].pid), '/T', '/F'], capture_output=True, timeout=10)",
 "subprocess.run(['taskkill', '/PID', str(row['proc'].pid), '/T', '/F'],\n                           capture_output=True, timeout=10,\n                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))",1),
("start_new_session=os.name != 'nt')",
 "start_new_session=os.name != 'nt',\n                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))",2),
]
modified=source
for before,after,expected in needle:
    count=modified.count(before)
    if count==0 and modified.count(after)==expected:
        continue
    if count!=expected:
        raise SystemExit(f"LIVE_SOURCE_MISMATCH expected {expected} saw {count} for {before[:35]!r}")
    modified=modified.replace(before,after)
ast.parse(modified,filename=str(target))
if modified==source:
    print("LIVE_WORKER_ALREADY_NO_CONSOLE_PATCHED")
else:
    state=Path(os.environ["LOCALAPPDATA"])/"AsterionControl"/"backups"
    state.mkdir(parents=True,exist_ok=True)
    backup=state/("app-before-no-console-"+time.strftime("%Y%m%d-%H%M%S")+".py")
    shutil.copy2(target,backup)
    temp=target.with_suffix(".py.no-console-new")
    temp.write_text(modified,encoding="utf-8")
    os.replace(temp,target)
    print("LIVE_WORKER_NO_CONSOLE_PATCHED_BACKUP_CREATED")
    print("RUNNING_WORKER_UNCHANGED_UNTIL_IDLE_RESTART")
print("FOUR_SUBPROCESS_CALL_SITES_CHECKED")
