"""Careful field instrumentation of the *existing* deployed phone WSS relay.

Preserves production drift, credentials, pairing and native endpoints.
Dry-run is default; --apply requires an exact source signature and preserves
a backup outside the service tree. Does NOT restart processes.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def patch(source: str) -> str:
    if "from .diagnostic_core import try_record" in source:
        return source
    import_anchor = "from .phone_bridge import load as load_registered_phone\n"
    denial = '''    if not header.startswith("Bearer ") or not _authorized(header[7:]):
        await ws.close(code=1008)
        return'''
    denial_new = '''    if not header.startswith("Bearer ") or not _authorized(header[7:]):
        try_record("security_failure",component="phone_wss_relay",severity="warning",
                   state="failed",attributes={"stage":"authorization",
                     "reason":"missing_bearer_header" if not header.startswith("Bearer ") else "unapproved_phone_key"})
        await ws.close(code=1008)
        return'''
    active = '''    if _active is not None:
        # Never replace an in-flight session and silently replay its requests.
        await ws.close(code=1008)
        return'''
    active_new = '''    if _active is not None:
        # Never replace an in-flight session and silently replay its requests.
        try_record("transport_error",component="phone_wss_relay",severity="warning",
                   state="failed",attributes={"stage":"upgrade","reason":"session_already_active"})
        await ws.close(code=1008)
        return'''
    accept = '''    await ws.accept()
    _active = ws
    try:'''
    accept_new = '''    await ws.accept()
    _active = ws
    try_record("phone_connected",component="phone_wss_relay",state="connected",
               attributes={"stage":"websocket_accepted"})
    try:'''
    for expected in (import_anchor,denial,active,accept):
        if source.count(expected)!=1:
            raise RuntimeError("Deployed relay differs from expected signature; no writes made")
    source=source.replace(import_anchor, "from .diagnostic_core import try_record\n"+import_anchor)
    source=source.replace(denial,denial_new).replace(active,active_new).replace(accept,accept_new)
    ast.parse(source)
    return source


def main():
    args=argparse.ArgumentParser()
    args.add_argument("--apply",action="store_true")
    options=args.parse_args()
    if os.name!="nt":
        raise RuntimeError("Owner Windows runtime only")
    release=Path(os.environ.get("ASTERION_DEPLOYED_CONTROL","D:/AsterionControlRelease")).resolve()
    stage=Path(__file__).resolve().parent.parent
    target=release/"asterion_remote/native_phone_live.py"
    addition=release/"asterion_remote/diagnostic_core.py"
    new_diag=stage/"asterion_remote/diagnostic_core.py"
    if not target.is_file() or not new_diag.is_file():
        raise RuntimeError("Production relay or source diagnostics unavailable")
    old_bytes=target.read_bytes()
    raw_text=old_bytes.decode("utf-8")
    # Keep the deployed file's original Windows CRLF style. Never rewrite
    # unrelated production lines merely because the staged source is LF.
    crlf="\r\n" in raw_text
    normalized=raw_text.replace("\r\n","\n")
    patched=patch(normalized)
    updated=(patched.replace("\n","\r\n") if crlf else patched).encode("utf-8")
    diagnostics=new_diag.read_bytes()
    ast.parse(diagnostics.decode("utf-8"))
    result={"mode":"apply" if options.apply else "dry_run",
            "relay_old_sha256":digest(old_bytes),
            "relay_new_sha256":digest(updated),
            "diagnostic_module_sha256":digest(diagnostics),
            "relay_will_change":old_bytes!=updated,
            "production_branch_preserved":True}
    if not options.apply:
        print(json.dumps(result,sort_keys=True))
        return
    state=Path(os.environ["LOCALAPPDATA"])/"AsterionControl"/"deployment-backups"
    state.mkdir(parents=True,exist_ok=True)
    backup=state/("native_phone_live-"+digest(old_bytes)+".py")
    if not backup.exists():
        with backup.open("xb") as f:
            f.write(old_bytes)
            f.flush()
            os.fsync(f.fileno())
    elif backup.read_bytes()!=old_bytes:
        raise RuntimeError("Backup hash collision, refusing deployment")
    module_tmp=addition.with_suffix(".py.new")
    relay_tmp=target.with_suffix(".py.new")
    module_tmp.write_bytes(diagnostics)
    relay_tmp.write_bytes(updated)
    try:
        module_tmp.replace(addition)
        relay_tmp.replace(target)
    except BaseException:
        target.write_bytes(old_bytes)
        raise
    if target.read_bytes()!=updated or addition.read_bytes()!=diagnostics:
        target.write_bytes(old_bytes)
        raise RuntimeError("Deployment checksum mismatch; relay file restored")
    result["backed_up"]=True
    result["source_installed"]=True
    result["service_restarted"]=False
    print(json.dumps(result,sort_keys=True))


if __name__=="__main__":
    main()
