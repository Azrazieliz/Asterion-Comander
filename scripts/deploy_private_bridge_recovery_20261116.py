"""Safely deploy the authenticated Git relay/watchdog recovery to the owner's PC.

Default dry-run. Does not restart or kill any process: the already installed
minute watchdog may reload a *stalled and idle* worker after publishing the
current native job's receipt. Never edits pairing, app data, APKs, keystores,
WSS relay, user repositories or model files.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

FILES=(
    "asterion_remote/github_bridge.py",
    "asterion_remote/github_bridge_git.py",
    "scripts/control_repair_watchdog.ps1",
)
EXPECTED_ORIGIN="azrazieliz/asterion-comander"
EXPECTED_BRANCH="work/control-0927-overnight-cycles-20261111"

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def run_git(source: Path, *args: str) -> str:
    command=subprocess.run(["git","-C",str(source),*args],
        check=True,capture_output=True,text=True,timeout=20)
    return command.stdout.strip()

def preflight(source: Path, production: Path):
    if os.name!="nt":
        raise RuntimeError("This deployment is only supported on the owner Windows computer")
    if production.resolve().as_posix().lower()!="d:/asterioncontrolrelease":
        raise RuntimeError("Unexpected production directory; refusing")
    if not (source/".git").exists():
        raise RuntimeError("Source must be an existing inspected Git checkout")
    if source.resolve()==production.resolve():
        raise RuntimeError("Source and live installation cannot be the same")
    origin=run_git(source,"remote","get-url","origin").lower().rstrip("/")
    if EXPECTED_ORIGIN not in origin or not origin.endswith(
        ("asterion-comander","asterion-comander.git")):
        raise RuntimeError("Source repository is not the authorized Control project")
    branch=run_git(source,"branch","--show-current")
    if branch!=EXPECTED_BRANCH:
        raise RuntimeError("Source branch does not match the validated feature branch")
    if run_git(source,"status","--porcelain","--untracked-files=no"):
        raise RuntimeError("Source checkout contains uncommitted tracked changes")
    if not (production/"asterion_remote"/"github_bridge_git.py").is_file():
        raise RuntimeError("Existing private Git relay missing; no replacement install authorized")
    if not (production/"scripts"/"start_git_bridge.ps1").is_file():
        raise RuntimeError("Existing owner bridge supervisor missing")
    updated={}
    old={}
    for rel in FILES:
        source_file=source/rel
        target=production/rel
        if not source_file.is_file() or not target.is_file():
            raise RuntimeError("Expected existing source/production file missing: "+rel)
        data=source_file.read_bytes()
        if rel.endswith(".py"):
            ast.parse(data.decode("utf8"),filename=rel)
        else:
            # Parse with the actual Windows PowerShell grammar, no execution.
            check=subprocess.run(["powershell.exe","-NoProfile","-NonInteractive",
                 "-Command",
                 "$e=$null;$t=$null;[System.Management.Automation.Language.Parser]::ParseFile("
                 +"'"+str(source_file).replace("'","''")+"',[ref]$t,[ref]$e)|Out-Null;"
                 +"if($e.Count){exit 1}"],
                 check=False,capture_output=True,timeout=20)
            if check.returncode:
                raise RuntimeError("Watchdog PowerShell syntax invalid")
        updated[rel]=data
        old[rel]=target.read_bytes()
    gitcode=updated["asterion_remote/github_bridge_git.py"].decode()
    watchdog=updated["scripts/control_repair_watchdog.ps1"].decode()
    if ("control-git-bridge-health.json" not in gitcode or
        "health('processing',inflight_id=identity)" not in gitcode or
        "preserve_dirty_receipts" not in gitcode or
        "reconcile_jobs" not in gitcode):
        raise RuntimeError("Git relay safety contract not present")
    if ("control-git-bridge-health.json" not in watchdog or
        "$jobsKnown -and -not $activeJobs -and $cooldown" not in watchdog or
        "if(-not [string]::IsNullOrWhiteSpace($inflight))" not in watchdog):
        raise RuntimeError("Idle-only watchdog recovery contract missing")
    return updated,old

def deploy(source: Path, production: Path, apply: bool=False):
    updated,previous=preflight(source,production)
    files={rel:{"previous_sha256":sha(previous[rel]),
                "new_sha256":sha(updated[rel]),
                "changed":updated[rel]!=previous[rel]} for rel in FILES}
    report={"ok":True,"mode":"apply" if apply else "dry_run",
            "files":files,"credentials_modified":False,
            "pairing_modified":False,"android_modified":False,
            "service_restarted":False}
    if not apply:
        return report
    state=Path(os.environ["LOCALAPPDATA"])/"AsterionControl"
    backup_root=state/"deployment-backups"/"private-relay-recovery-v1"
    backup_root.mkdir(parents=True,exist_ok=True)
    for rel,data in previous.items():
        backup=backup_root/(rel.replace("/","__")+"-"+sha(data)+".bak")
        try:
            with backup.open("xb") as out:
                out.write(data)
                out.flush()
                os.fsync(out.fileno())
        except FileExistsError:
            if backup.read_bytes()!=data:
                raise RuntimeError("Existing immutable backup has unexpected contents")
    installed=[]
    try:
        for rel,data in updated.items():
            target=production/rel
            if data==previous[rel]:
                continue
            fd,tmp=tempfile.mkstemp(prefix=".asterion-relay-recovery-",dir=target.parent)
            try:
                with os.fdopen(fd,"wb") as out:
                    out.write(data)
                    out.flush()
                    os.fsync(out.fileno())
                os.replace(tmp,target)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
            installed.append(rel)
            if sha(target.read_bytes())!=sha(data):
                raise RuntimeError("Production file hash mismatch: "+rel)
    except BaseException:
        for rel in reversed(installed):
            (production/rel).write_bytes(previous[rel])
        raise
    report["installed_files"]=installed
    report["backup_dir"]=str(backup_root)
    report["pending_supervised_reload"]=bool(installed)
    return report

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--production",default="D:/AsterionControlRelease")
    args=parser.parse_args()
    result=deploy(Path(__file__).resolve().parents[1],
                  Path(args.production),apply=args.apply)
    print(json.dumps(result,sort_keys=True),flush=True)

if __name__=="__main__":
    main()
