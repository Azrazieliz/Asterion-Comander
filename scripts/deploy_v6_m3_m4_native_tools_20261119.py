"""Guarded additive deployment of exact M3 signed-intent and M4 native AI tools.

Patch the EXISTING original Windows Control API/WSS relay implementation.
Never replace owner pairing, signer, running jobs, listener topology, or general
file/command permissions. Do not restart workers inside this procedure; the
original busy-guarded API and owner-relay reloads are separate acceptance gates.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

SOURCE=Path(__file__).resolve().parents[1]
PRODUCTION=Path("D:/AsterionControlRelease")
BRANCH="work/control-0927-overnight-cycles-20261111"
RPC="asterion_remote/native_phone_rpc.py"
BRIDGE="asterion_remote/phone_bridge.py"
ROUTES="asterion_remote/native_routes.py"
FILES=(RPC,BRIDGE,ROUTES)

def digest(payload:bytes)->str:
    return hashlib.sha256(payload).hexdigest()

def assert_source():
    if os.name!="nt" or not (SOURCE/".git").is_dir():
        raise RuntimeError("Original isolated Windows source checkout unavailable")
    def git(*args):
        return subprocess.run(["git","-C",str(SOURCE),*args],
             check=True,capture_output=True,text=True,timeout=20).stdout.strip()
    if git("branch","--show-current")!=BRANCH:
        raise RuntimeError("Unexpected owner-approved source branch")
    if not git("remote","get-url","origin").lower().endswith((
       "azrazieliz/asterion-comander.git","azrazieliz/asterion-comander")):
        raise RuntimeError("Not the canonical Control repository")
    if git("status","--porcelain","--untracked-files=no"):
        raise RuntimeError("Source has uncommitted tracked changes")
    if not (PRODUCTION/"asterion_remote/app.py").is_file():
        raise RuntimeError("Existing owner Windows API missing")

def replace_once(value:str,old:str,new:str,area:str)->str:
    if value.count(old)!=1:
        raise RuntimeError("Unexpected owner production source for "+area)
    return value.replace(old,new,1)

def source_fragment(file:str,start:str,end:str)->str:
    content=(SOURCE/file).read_text("utf8").replace("\r\n","\n")
    a=content.index(start)
    b=content.index(end,a)
    return content[a:b]

def patch_rpc(code:str)->str:
    addition=source_fragment(RPC,
        '    ("POST", "/app-bridge/capabilities"): "control_phone_app_capabilities",',
        "}\n") if False else ""
    # The exact v1 tool routing table is the only permitted mutation.
    before='    ("GET", "/app-bridge/apps"): "control_phone_app_bridges",'
    if '"control_phone_ai_submit"' in code:
        for necessary in ("control_phone_app_capabilities","control_phone_intent_dispatch",
                          "control_phone_ai_model_status","control_phone_ai_job",
                          "control_phone_ai_cancel"):
            if necessary not in code:
                raise RuntimeError("Partial original RPC action map; reconcile before deployment")
        return code
    source=(SOURCE/RPC).read_text("utf8").replace("\r\n","\n")
    start=source.index('    ("POST", "/app-bridge/capabilities"): "control_phone_app_capabilities",')
    end=source.index("\n",source.index('    ("POST", "/ai/jobs/cancel"): "control_phone_ai_cancel",',start))+1
    snippet=source[start:end]
    return replace_once(code,before,before+"\n"+snippet.rstrip("\n"),RPC)

def patch_bridge(code:str)->str:
    source=(SOURCE/BRIDGE).read_text("utf8").replace("\r\n","\n")
    if "def request_native_only(" in code:
        fragment=source_fragment(BRIDGE,"def request_native_only(","def probe_native_wss_roundtrip(")
        if fragment.strip() not in code:
            raise RuntimeError("Owner native-only bridge differs; refusing replace")
    else:
        fragment=source_fragment(BRIDGE,"def request_native_only(","def probe_native_wss_roundtrip(")
        if "def probe_native_wss_roundtrip(" not in code or "_request_via_outbound_wss" not in code:
            raise RuntimeError("Original production does not have the approved WSS transport")
        code=replace_once(code,"def probe_native_wss_roundtrip(",fragment+
             "def probe_native_wss_roundtrip(",BRIDGE)
    required=[
        "'/app-bridge/capabilities'","'/intent/dispatch'",
        "'/ai/model/status'","'/ai/jobs/submit'","'/ai/jobs/status'","'/ai/jobs/cancel'",
    ]
    if all(x in code for x in required):
        return code
    marker="'/app-bridge/operation'"
    additions=", "+", ".join(x for x in required if x not in code)
    code=replace_once(code,marker,marker+additions,BRIDGE)
    if not all(x in code for x in required):
        raise RuntimeError("Original native WSS route allowlist still incomplete")
    return code

def patch_routes(code:str)->str:
    import_marker="from .phone_bridge import PairPhone, PhoneInput, register, request, load, probe_native_wss_roundtrip"
    full=import_marker+", request_native_only"
    if full not in code:
        code=replace_once(code,import_marker,full,ROUTES)
    source=(SOURCE/ROUTES).read_text("utf8").replace("\r\n","\n")
    snippet=source_fragment(ROUTES,"class AppCapabilityRead(BaseModel):",
                            "@router.post('/phone/app-bridge/operation')")
    if "def native_ai_submit(" in code:
        for required in ("def native_ai_model_status(", "def app_bridge_capabilities(",
                         "def phone_direct_intent(","def native_ai_job_status(",
                         "def native_ai_job_cancel("):
            if required not in code:
                raise RuntimeError("Partial original native routes; reconcile before deployment")
        return code
    anchor="@router.post('/phone/app-bridge/operation')"
    if "class AppCapabilityRead(BaseModel):" in code:
        raise RuntimeError("Partial signed specialist routes already installed")
    return replace_once(code,anchor,snippet+anchor,ROUTES)

def plan():
    assert_source()
    transforms={RPC:patch_rpc,BRIDGE:patch_bridge,ROUTES:patch_routes}
    staged={}
    results={}
    for relative in FILES:
        destination=PRODUCTION/relative
        original=destination.read_bytes()
        line_end="\r\n" if b"\r\n" in original else "\n"
        decoded=original.decode("utf8").replace("\r\n","\n")
        patched=transforms[relative](decoded)
        ast.parse(patched,filename=relative)
        updated=patched.replace("\n",line_end).encode("utf8")
        staged[relative]=(original,updated)
        results[relative]={
            "changed":original!=updated,
            "previous_sha256":digest(original),
            "target_sha256":digest(updated),
            "bytes":len(updated),
        }
    return staged,results

def deploy(apply:bool):
    files,results=plan()
    receipt={"ok":True,"mode":"apply" if apply else "dry_run",
             "files":results,"original_windows_restarted":False,
             "original_native_relay_restarted":False,"signer_changed":False,
             "pairing_changed":False,"new_engine_created":False}
    if not apply:return receipt
    backup=(Path(os.environ["LOCALAPPDATA"])/"AsterionControl"/
            "deployment-backups"/"v6-m3m4-native-tools")
    backup.mkdir(parents=True,exist_ok=True)
    changed=[]
    try:
        for name,(before,after) in files.items():
            if before==after:continue
            record=backup/(name.replace("/","__")+"-"+digest(before)+".bak")
            try:
                with record.open("xb") as f:
                    f.write(before);f.flush();os.fsync(f.fileno())
            except FileExistsError:
                if record.read_bytes()!=before:
                    raise RuntimeError("Original immutable backup differs for "+name)
        for name,(before,after) in files.items():
            if before==after:continue
            destination=PRODUCTION/name
            fd,tmp=tempfile.mkstemp(prefix=".v6-native-",dir=destination.parent)
            try:
                with os.fdopen(fd,"wb") as f:
                    f.write(after);f.flush();os.fsync(f.fileno())
                os.replace(tmp,destination)
            finally:
                if os.path.exists(tmp):os.unlink(tmp)
            changed.append(name)
            if digest(destination.read_bytes())!=digest(after):
                raise RuntimeError("Post-deploy production hash mismatch")
    except BaseException:
        for name in reversed(changed):
            (PRODUCTION/name).write_bytes(files[name][0])
        raise
    receipt["deployed"]=changed
    receipt["backup_dir"]=str(backup)
    return receipt

if __name__=="__main__":
    arg=argparse.ArgumentParser()
    arg.add_argument("--apply",action="store_true")
    args=arg.parse_args()
    print(json.dumps(deploy(args.apply),sort_keys=True,separators=(",",":")),flush=True)
