"""Stage tested Windows diagnostics and mixed sessions without replacing working owner config.

Never touches pairing, API tokens, Android, signed APK, scripts/watchdog,
existing GitHub bridge or native relay. Backups are exact, content-addressed.
Default dry-run. --apply installs source only, then operator separately
restarts the *specific Windows Control worker* at a safe checkpoint.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import os
import subprocess
from pathlib import Path

FILES=("asterion_remote/app.py",
       "asterion_remote/diagnostic_core.py",
       "asterion_remote/diagnostic_routes.py",
       "asterion_remote/interaction_sessions.py")


def digest(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()


def patch_app(raw:bytes)->bytes:
    text=raw.decode("utf-8")
    crlf="\r\n" in text
    source=text.replace("\r\n","\n")
    imp="from .native_routes import router as phone_router"
    mount="app.include_router(phone_router)"
    if source.count(imp)!=1 or source.count(mount)!=1:
        raise RuntimeError("Live app import structure differs; refusing patch")
    if "from .diagnostic_routes import router as diagnostic_router" not in source:
        source=source.replace(imp,imp+"\nfrom .diagnostic_routes import router as diagnostic_router")
    if "app.include_router(diagnostic_router)" not in source:
        source=source.replace(mount,mount+"\napp.include_router(diagnostic_router)")
    ast.parse(source)
    return (source.replace("\n","\r\n") if crlf else source).encode("utf-8")


def main():
    arg=argparse.ArgumentParser()
    arg.add_argument("--apply",action="store_true")
    opt=arg.parse_args()
    if os.name!="nt":raise RuntimeError("Windows runtime required")
    stage=Path(__file__).resolve().parent.parent
    prod=Path(os.environ.get("ASTERION_DEPLOYED_CONTROL","D:/AsterionControlRelease"))
    if not (prod/".git").exists():raise RuntimeError("Production source identity missing")
    dirty=subprocess.run(["git","-C",str(prod),"status","--porcelain","--",
                          "asterion_remote/interaction_sessions.py"],
                         capture_output=True,text=True,check=True,timeout=10)
    if dirty.stdout.strip():
        # The previous approved deploy intentionally modified this tracked
        # production file without switching the original release branch.
        # Permit subsequent upgrades only if deployed bytes EXACTLY match
        # the audited stage. Otherwise preserve owner's unrelated edits.
        existing=prod/"asterion_remote/interaction_sessions.py"
        staged=stage/"asterion_remote/interaction_sessions.py"
        if not existing.exists() or existing.read_bytes()!=staged.read_bytes():
            raise RuntimeError("Production sessions changed outside our staged revision; abort")
    updates={}
    old={}
    for name in FILES:
        src=stage/name
        dst=prod/name
        if not src.exists():raise RuntimeError("Missing source "+name)
        previous=dst.read_bytes() if dst.exists() else None
        contents=patch_app(previous) if name.endswith("/app.py") else src.read_bytes()
        ast.parse(contents.decode("utf-8"))
        old[name]=previous
        updates[name]=contents
    overview={"mode":"apply" if opt.apply else "dry_run",
              "changes":{name:{"prior_exists":old[name] is not None,
                               "changed":old[name]!=updates[name],
                               "sha256":digest(updates[name])}
                         for name in FILES},
              "credentials_touched":False,"pairing_touched":False,
              "process_restarted":False}
    if not opt.apply:
        print(json.dumps(overview,sort_keys=True))
        return
    backup=Path(os.environ["LOCALAPPDATA"])/"AsterionControl"/"deployment-backups"
    backup.mkdir(parents=True,exist_ok=True)
    written=[]
    try:
        for name in FILES:
            dst=prod/name
            current=old[name]
            if current is not None and current!=updates[name]:
                name_safe=name.replace("/","_")
                saved=backup/(name_safe+"-"+digest(current)+".backup")
                if not saved.exists():
                    with saved.open("xb") as out:
                        out.write(current);out.flush();os.fsync(out.fileno())
                elif saved.read_bytes()!=current:
                    raise RuntimeError("Backup collision "+name)
            if current==updates[name]:continue
            tmp=dst.with_name(dst.name+".diagnostic-new")
            tmp.write_bytes(updates[name])
            tmp.replace(dst)
            written.append(name)
            if dst.read_bytes()!=updates[name]:
                raise RuntimeError("Checksum mismatch "+name)
    except BaseException:
        for name in reversed(written):
            dst=prod/name
            previous=old[name]
            if previous is None:dst.unlink(missing_ok=True)
            else:dst.write_bytes(previous)
        raise
    overview["installed_files"]=written
    overview["backed_up"]=True
    overview["process_restarted"]=False
    print(json.dumps(overview,sort_keys=True))


if __name__=="__main__":
    main()
