"""Additive, reversible diagnostics-only deployment to the EXISTING Windows Control.

The Android app, owner signer, installed data, pairing, agent keys, WSS relay,
watchdog, and Downloader source are never touched here. Default is dry-run.
Apply only from an isolated, tested checkout. No services are restarted.
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

FILES = (
    "asterion_remote/diagnostic_core.py",
    "asterion_remote/diagnostic_analysis.py",
    "asterion_remote/diagnostic_snapshot.py",
    "asterion_remote/diagnostic_routes.py",
    "asterion_remote/github_bridge.py",
    "asterion_remote/static/app.js",
    "asterion_remote/static/index.html",
    "asterion_remote/static/style.css",
)

def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def check(source: Path, dest: Path) -> dict:
    if source.resolve() == dest.resolve():
        raise RuntimeError("production_is_source")
    if not (source / ".git").is_dir() or not (dest / ".git").is_dir():
        raise RuntimeError("source_and_existing_production_git_identity_required")
    if not (dest / "asterion_remote/app.py").is_file():
        raise RuntimeError("production_control_application_missing")
    active = (dest / "asterion_remote/app.py").read_text("utf8")
    if ("app.include_router(diagnostic_router)" not in active or
            "from .diagnostic_routes import router as diagnostic_router" not in active):
        raise RuntimeError("existing_diagnostic_router_is_not_mounted")
    native = (dest / "asterion_remote/phone_bridge.py").read_text("utf8")
    if "/diagnostics/events" not in native or "/diagnostics/exit-history" not in native:
        raise RuntimeError("existing_native_phone_diagnostic_adapter_missing")
    status = subprocess.run(
        ["git", "-C", str(source), "status", "--porcelain",
         "--untracked-files=no"], capture_output=True, text=True,
        check=True, timeout=15)
    if status.stdout.strip():
        raise RuntimeError("source_checkout_not_reproducible")
    overview = {}
    for name in FILES:
        original = dest / name
        update = source / name
        if not update.is_file():
            raise RuntimeError("missing_tested_source:" + name)
        blob = update.read_bytes()
        if name.endswith(".py"):
            ast.parse(blob.decode("utf8"), filename=name)
        elif not blob or len(blob) > 256000:
            raise RuntimeError("invalid_static_asset:" + name)
        existing = original.read_bytes() if original.exists() else None
        overview[name] = {
            "changed": existing != blob,
            "prior_sha256": sha(existing) if existing is not None else None,
            "source_sha256": sha(blob),
            "new_file": existing is None,
        }
    return overview

def deploy(source: Path, dest: Path, *, apply: bool) -> dict:
    overview = check(source, dest)
    outcome = {
        "ok": True, "mode": "apply" if apply else "dry_run",
        "target": "existing_windows_control",
        "files": overview,
        "pairing_changed": False, "signer_changed": False,
        "android_package_changed": False, "service_restarted": False,
    }
    if not apply:
        return outcome
    backup_root = (
        Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        / "AsterionControl" / "deployment-backups" / "diagnostic_0932"
    )
    backup_root.mkdir(parents=True, exist_ok=True)
    originals: dict[str, bytes | None] = {}
    written: list[str] = []
    try:
        for name in FILES:
            previous = dest / name
            saved = previous.read_bytes() if previous.exists() else None
            originals[name] = saved
            if saved is not None:
                backup_name = name.replace("/", "__") + "-" + sha(saved) + ".bak"
                backup = backup_root / backup_name
                try:
                    with backup.open("xb") as handle:
                        handle.write(saved)
                        handle.flush()
                        os.fsync(handle.fileno())
                except FileExistsError:
                    if backup.read_bytes() != saved:
                        raise RuntimeError("backup_integrity_mismatch:" + name)
        for name in FILES:
            if not overview[name]["changed"]:
                continue
            target = dest / name
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, staging = tempfile.mkstemp(prefix=".control-diagnostic-",
                                           dir=str(target.parent))
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write((source / name).read_bytes())
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(staging, target)
            finally:
                if os.path.exists(staging):
                    os.unlink(staging)
            written.append(name)
            if sha(target.read_bytes()) != overview[name]["source_sha256"]:
                raise RuntimeError("postwrite_checksum_mismatch:" + name)
    except BaseException:
        for name in reversed(written):
            target = dest / name
            previous = originals[name]
            if previous is None:
                target.unlink(missing_ok=True)
            else:
                target.write_bytes(previous)
        raise
    outcome["installed_files"] = written
    outcome["backups"] = str(backup_root)
    return outcome

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--production", default="D:/AsterionControlRelease")
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    dest = Path(args.production).resolve()
    print(json.dumps(deploy(source, dest, apply=args.apply),
                     sort_keys=True), flush=True)

if __name__ == "__main__":
    main()
