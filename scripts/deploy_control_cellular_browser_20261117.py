"""Guarded install of approved Control browser/cellular backend into existing Windows worker.

Preserves production-only code, pairing, services, account data and tokens.
Does not restart workers; a separate verified idle restart is required.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]
EXPECTED_TARGET = Path("D:/AsterionControlRelease")
PHONE_BRIDGE_BASE_BLOB = "2a38f11ef389747957ae3d44f4765d92887ba372"
APP_IMPORT = "from .browser_crawler import router as browser_crawler_router"
APP_ANCHOR = "from .recovery import router as recovery_router"
APP_ROUTE = "app.include_router(browser_crawler_router)"
APP_ROUTE_ANCHOR = "app.include_router(recovery_router)"
RELAY_IMPORT = "from .native_phone_rpc import router as local_rpc_router"
RELAY_ANCHOR = "app.include_router(phone_router)"
RELAY_ROUTE = "app.include_router(local_rpc_router)"
FILES = (
    "asterion_remote/phone_bridge.py",
    "asterion_remote/app.py",
    "asterion_remote/native_phone_relay.py",
    "asterion_remote/native_phone_rpc.py",
    "asterion_remote/browser_crawler.py",
)


def git_blob(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def plan(target: Path) -> dict[Path, bytes]:
    changes = {}
    for name in FILES:
        original_path = target / name
        source_path = SOURCE / name
        code = source_path.read_text("utf-8")
        if name.endswith("/phone_bridge.py"):
            canonical = subprocess.run(["git", "hash-object", "--", str(original_path)],
                cwd=target, capture_output=True, text=True, check=False) if original_path.exists() else None
            if canonical is None or canonical.returncode or canonical.stdout.strip() != PHONE_BRIDGE_BASE_BLOB:
                raise RuntimeError("Production phone bridge differs from audited baseline; manual three-way merge required")
        elif name.endswith("/app.py"):
            original = original_path.read_bytes().decode("utf-8")
            newline = "\\r\\n" if "\\r\\n" in original else "\\n"
            if APP_IMPORT in original or APP_ROUTE in original:
                if APP_IMPORT in original and APP_ROUTE in original: code = original
                else: raise RuntimeError("Partially installed Browser API hook")
            else:
                if APP_ANCHOR not in original or APP_ROUTE_ANCHOR not in original:
                    raise RuntimeError("Production API lacks safe Browser insertion anchors")
                code = original.replace(APP_ANCHOR, APP_ANCHOR+"\n"+APP_IMPORT, 1)
                code = code.replace(APP_ROUTE_ANCHOR, APP_ROUTE_ANCHOR+"\n"+APP_ROUTE, 1)
        elif name.endswith("/native_phone_relay.py"):
            original = original_path.read_bytes().decode("utf-8")
            newline = "\\r\\n" if "\\r\\n" in original else "\\n"
            if RELAY_IMPORT in original or RELAY_ROUTE in original:
                if RELAY_IMPORT in original and RELAY_ROUTE in original: code=original
                else: raise RuntimeError("Partially installed native relay hook")
            else:
                if RELAY_ANCHOR not in original:
                    raise RuntimeError("Existing native relay lacks required route insertion anchor")
                code = original.replace(RELAY_ANCHOR, RELAY_ANCHOR+
                    "\n\n# Trusted Windows-local RPC onto the existing outbound phone WebSocket.\n"+
                    RELAY_IMPORT+"\n"+RELAY_ROUTE, 1)
        elif original_path.exists() and original_path.read_text("utf-8") != code:
            raise RuntimeError("Existing production-only module would be overwritten: "+name)
        ast.parse(code, filename=name)
        changes[original_path] = code.encode("utf-8")
    return changes


def main():
    args = argparse.ArgumentParser()
    args.add_argument("--apply", action="store_true")
    options = args.parse_args()
    target = EXPECTED_TARGET
    if not target.is_dir():
        raise RuntimeError("Existing Control production directory missing")
    changes = plan(target)
    print(json.dumps({"stage": "validated", "changed_modules": [
        str(path.relative_to(target)) for path, body in changes.items()
        if not path.exists() or body != path.read_bytes()]}, separators=(",", ":")), flush=True)
    if not options.apply:
        return
    backup = Path(os.environ["LOCALAPPDATA"]) / "AsterionControl" / "backup-cellular-browser-20261117"
    backup.mkdir(parents=True, exist_ok=True)
    prior: dict[Path, bytes | None] = {}
    try:
        for path, body in changes.items():
            before = path.read_bytes() if path.exists() else None
            if before == body:
                continue
            prior[path] = before
            if before is not None:
                saved = backup / (path.name + "-" + hashlib.sha256(before).hexdigest() + ".backup")
                if not saved.exists():
                    with saved.open("xb") as stream:
                        stream.write(before)
                        stream.flush()
                        os.fsync(stream.fileno())
            tmp = path.with_name(path.name + ".asterion.new")
            tmp.write_bytes(body)
            os.replace(tmp, path)
            if path.read_bytes() != body:
                raise RuntimeError("Installed Control source hash mismatch: " + path.name)
        compile_run = subprocess.run(
            [sys.executable, "-m", "compileall", "-q", *(str(p) for p in changes)],
            cwd=target, check=False, timeout=60, capture_output=True, text=True)
        if compile_run.returncode:
            raise RuntimeError("Production Python compile failed: " + compile_run.stderr[-300:])
        check = subprocess.run(
            [sys.executable, "-c", "import asterion_remote.app; import asterion_remote.native_phone_relay; print('imports_ok')"],
            cwd=target, check=False, timeout=40, capture_output=True, text=True)
        if check.returncode or "imports_ok" not in check.stdout:
            raise RuntimeError("Production startup import regression: " + check.stderr[-400:])
    except Exception:
        for path, before in reversed(list(prior.items())):
            if before is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(before)
        raise
    print(json.dumps({"stage": "installed_verified", "backed_up": True,
        "module_count": len(prior), "running_processes_restarted": False,
        "owner_keys_or_pairing_changed": False}, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()
