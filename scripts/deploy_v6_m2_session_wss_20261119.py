"""Deploy the M2 WSS-first mixed-session fix into the original Windows worker.

No new transport, token, pairing, Android package, signer, or gateway is created.
Refuses ANY production change from the exact inspected original source revision.
The native Windows API must be safely reloaded separately after the calling job.
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

SOURCE = Path(__file__).resolve().parents[1]
TARGET = Path("D:/AsterionControlRelease")
RELATIVE = "asterion_remote/interaction_sessions.py"
# Genuine fresh production read-only audit: 2026-11-19; do not auto-patch unknown code.
ORIGINAL_PRODUCTION_SHA256 = "5c0cc26155dbebb1942ec2d0f5775a1fb67af3093afbe9b949f631ee3a3e56b6"
BRANCH = "work/control-0927-overnight-cycles-20261111"

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def verify_checkout() -> None:
    if os.name != "nt" or not (SOURCE / ".git").is_dir():
        raise RuntimeError("Original Windows and independent source checkout required")
    def git(*args):
        result = subprocess.run(["git","-C",str(SOURCE),*args],check=True,
                                capture_output=True,text=True,timeout=20)
        return result.stdout.strip()
    origin = git("remote","get-url","origin").lower()
    if not origin.endswith(("azrazieliz/asterion-comander",
                            "azrazieliz/asterion-comander.git")):
        raise RuntimeError("Wrong source repository")
    if git("branch","--show-current") != BRANCH:
        raise RuntimeError("Source branch not owner-approved")
    if git("status","--porcelain","--untracked-files=no"):
        raise RuntimeError("Uncommitted source checkout; refusing production write")
    if not (TARGET / "asterion_remote" / "app.py").is_file():
        raise RuntimeError("Original Windows Control service missing")

def plan() -> dict:
    verify_checkout()
    target = TARGET / RELATIVE
    original = target.read_bytes()
    current = sha(original)
    source = (SOURCE / RELATIVE).read_text("utf8")
    if not all(k in source for k in (
        "request as phone_request",
        'phone_request("/input","POST",data,timeout=8.0)',
        'phone_request("/ui",timeout=8.0)',
        "session_journal.reserve_if_new",
        "if len(_jobs)>200:",
    )):
        raise RuntimeError("M2 source code fails required safe native transport contract")
    if "httpx.Client(" in source:
        raise RuntimeError("M2 source still bypasses original primary WSS")
    ast.parse(source, filename=RELATIVE)
    # Preserve owner Windows source CRLF formatting and private configuration.
    changed = (source.replace("\n","\r\n") if b"\r\n" in original else source).encode("utf8")
    if current != ORIGINAL_PRODUCTION_SHA256 and original != changed:
        raise RuntimeError("Owner's interaction session source differs from audited baseline")
    return {"old":original,"new":changed,"prior_sha256":current,
            "new_sha256":sha(changed),"changed":original != changed}

def deploy(apply: bool) -> dict:
    p = plan()
    result = {"ok":True,"mode":"apply" if apply else "dry_run",
              "file":RELATIVE,"changed":p["changed"],
              "prior_sha256":p["prior_sha256"],
              "new_sha256":p["new_sha256"],
              "session_service_restarted":False,
              "pairing_changed":False,"signer_changed":False,
              "android_changed":False,"native_relay_changed":False}
    if not apply or not p["changed"]:
        return result
    backup = (Path(os.environ["LOCALAPPDATA"]) / "AsterionControl" /
              "deployment-backups"/"v6-m2-mixed-sessions")
    backup.mkdir(parents=True, exist_ok=True)
    prior = backup / ("interaction_sessions.py-"+p["prior_sha256"]+".bak")
    try:
        with prior.open("xb") as handle:
            handle.write(p["old"])
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        if prior.read_bytes()!=p["old"]:
            raise RuntimeError("Immutable existing backup mismatch")
    dest = TARGET / RELATIVE
    descriptor,tmp = tempfile.mkstemp(prefix=".asterion-m2-wss-",dir=dest.parent)
    try:
        with os.fdopen(descriptor,"wb") as handle:
            handle.write(p["new"])
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp,dest)
        if sha(dest.read_bytes())!=p["new_sha256"]:
            raise RuntimeError("Installed native session checksum mismatch")
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        dest.write_bytes(p["old"])
        raise
    result["deployed"] = True
    result["backup_sha_verified"] = sha(prior.read_bytes())==p["prior_sha256"]
    return result

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    print(json.dumps(deploy(args.apply),sort_keys=True),flush=True)
