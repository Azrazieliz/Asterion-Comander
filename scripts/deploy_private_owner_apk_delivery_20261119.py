"""Backup-first additive activation of a single owner-signed release download.

Adds ONLY the vetted, IP-restricted endpoint to the original Windows API,
not a new listener/gateway, pairing, credential, engine or phone change.
Must be restarted with the existing supervised one-shot Windows API reload
after the caller's pc_command is complete.
"""
from __future__ import annotations
import argparse,ast,hashlib,json,os,subprocess,tempfile,time
from pathlib import Path

SOURCE=Path(__file__).resolve().parents[1]
TARGET=Path("D:/AsterionControlRelease")
BRANCH="work/control-0927-overnight-cycles-20261111"
APP=Path("asterion_remote/app.py")
ROUTE=Path("asterion_remote/owner_apk_delivery.py")
APK=Path("D:/AsterionControlV6M0_20261119/dist/Asterion-Control-v0.9.38-release.apk")
SHA="31c10e86409c9183fa952c5079401eadddc879bed28f8f3c74c4f45de2440f7a"
SIZE=505163972

def digest(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def guard():
    if os.name!="nt" or not (SOURCE/".git").is_dir():
        raise RuntimeError("Expected original owner Windows isolated Git checkout")
    def git(*args):
        return subprocess.check_output(["git","-C",str(SOURCE),*args],
                    timeout=20,text=True).strip()
    if not git("remote","get-url","origin").lower().endswith((
         "azrazieliz/asterion-comander","azrazieliz/asterion-comander.git")):
        raise RuntimeError("Unexpected original repository")
    if git("branch","--show-current")!=BRANCH or git("status","--porcelain","--untracked-files=no"):
        raise RuntimeError("Only committed approved source branch can deploy")
    if not (TARGET/APP).is_file() or not (TARGET/"scripts/reload_windows_worker_once.py").is_file():
        raise RuntimeError("Original installed Windows service/supervisor not present")
    if APK.stat().st_size!=SIZE:
        raise RuntimeError("Original signed APK size mismatch")
    h=hashlib.sha256()
    with APK.open("rb") as inp:
        for chunk in iter(lambda:inp.read(1024*1024),b""):h.update(chunk)
    if h.hexdigest()!=SHA:
        raise RuntimeError("Original owner-signed APK SHA256 mismatch")

def plan():
    guard()
    target=TARGET/APP
    current=target.read_bytes()
    crlf=b"\r\n" in current
    text=current.decode("utf8").replace("\r\n","\n")
    source=(SOURCE/ROUTE).read_text("utf8")
    ast.parse(source,filename=str(ROUTE))
    if "OWNER" in source and "include_in_schema=False" not in source:
        raise RuntimeError("Private route security checks incomplete")
    import_at="from .browser_crawler import router as browser_crawler_router\n"
    import_line="from .owner_apk_delivery import router as owner_apk_delivery_router\n"
    include_at="app.include_router(browser_crawler_router)\n"
    include_line="app.include_router(owner_apk_delivery_router)\n"
    if import_line not in text:
        if text.count(import_at)!=1:raise RuntimeError("Original service import anchor different")
        text=text.replace(import_at,import_at+import_line)
    if include_line not in text:
        if text.count(include_at)!=1:raise RuntimeError("Original router anchor different")
        text=text.replace(include_at,include_at+include_line)
    ast.parse(text,filename=str(APP))
    new=(text.replace("\n","\r\n") if crlf else text).encode("utf8")
    other=TARGET/ROUTE
    if other.exists() and other.read_bytes()!=source.encode("utf8"):
        raise RuntimeError("Owner already has different private release route; refuse overwrite")
    return [(target,current,new),(other,other.read_bytes() if other.exists() else None,
                               source.encode("utf8"))]

def install(apply:bool):
    changes=plan()
    output={"ok":True,"dry_run":not apply,"source_sha":subprocess.check_output(
        ["git","-C",str(SOURCE),"rev-parse","HEAD"],text=True).strip(),
        "files":[{"path":p.relative_to(TARGET).as_posix(),"changed":o!=n,
                  "sha256":digest(n)} for p,o,n in changes],
        "original_service_restarted":False,
        "pairing_changed":False,"credentials_changed":False,
        "phone_changed":False}
    if not apply:return output
    folder=Path(os.environ["LOCALAPPDATA"])/"AsterionControl"/"deployment-backups"/"v6-0938-apk-route"
    folder.mkdir(parents=True,exist_ok=True)
    applied=[]
    try:
        for path,prior,new in changes:
            if prior==new:continue
            if prior is not None:
                backup=folder/(path.name+"-"+digest(prior)+".bak")
                if not backup.exists():
                    with backup.open("xb") as f:f.write(prior);f.flush();os.fsync(f.fileno())
                elif backup.read_bytes()!=prior:
                    raise RuntimeError("Conflicting immutable production backup")
            fd,tmp=tempfile.mkstemp(prefix=".asterion-release-",dir=path.parent)
            try:
                with os.fdopen(fd,"wb") as f:
                    f.write(new);f.flush();os.fsync(f.fileno())
                os.replace(tmp,path)
            finally:
                if os.path.exists(tmp):os.unlink(tmp)
            applied.append((path,prior))
            if path.read_bytes()!=new:raise RuntimeError("Additive deployment checksum failed")
    except BaseException:
        for path,prior in reversed(applied):
            if prior is None:path.unlink(missing_ok=True)
            else:path.write_bytes(prior)
        raise
    output["deployed"]=True
    output["original_service_restarted"]=False
    return output

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--apply",action="store_true")
    o=ap.parse_args()
    print(json.dumps(install(o.apply),sort_keys=True),flush=True)
