"""Additive, backup-first deployment to the ORIGINAL Windows Control installation.

Only applies independently tested P-1 safety fixes. No service restart, APK,
signing key, Android pairing, user data, partner engines or gateway is altered.
Production may have owner-specific code: merge the narrow audited functions
instead of overwriting the original modules wholesale.
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
BRANCH = "work/control-0927-overnight-cycles-20261111"
RELAY = "scripts/reload_native_wss_after_idle_20261119.ps1"
WATCHDOG = "scripts/control_repair_watchdog.ps1"
GIT = "asterion_remote/github_bridge_git.py"
PHONE = "asterion_remote/phone_bridge.py"
ROUTES = "asterion_remote/native_routes.py"
FILES = (GIT, PHONE, ROUTES, WATCHDOG, RELAY)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verified_checkout():
    if os.name != "nt" or not (SOURCE / ".git").is_dir():
        raise RuntimeError("An isolated Windows Control Git checkout is required")
    origin = subprocess.run(["git", "-C", str(SOURCE), "remote", "get-url", "origin"],
                            check=True, capture_output=True, text=True, timeout=15).stdout.strip().lower()
    if not origin.endswith(("azrazieliz/asterion-comander.git", "azrazieliz/asterion-comander")):
        raise RuntimeError("Unexpected source repository; refusing deployment")
    head = subprocess.run(["git", "-C", str(SOURCE), "branch", "--show-current"],
                          check=True, capture_output=True, text=True, timeout=15).stdout.strip()
    if head != BRANCH:
        raise RuntimeError("Unapproved source branch")
    dirty = subprocess.run(["git", "-C", str(SOURCE), "status", "--porcelain",
                            "--untracked-files=no"], check=True, capture_output=True,
                           text=True, timeout=15).stdout
    if dirty.strip():
        raise RuntimeError("Tracked source changes are not committed")
    if not (TARGET / "asterion_remote/native_phone_relay.py").is_file():
        raise RuntimeError("Original Windows Control relay missing")
    if not (TARGET / ".venv/Scripts/python.exe").is_file():
        raise RuntimeError("Original Windows Control runtime missing")


def unique_replace(text: str, before: str, after: str, name: str) -> str:
    if text.count(before) != 1:
        raise RuntimeError("Owner production differs from exact approved " + name + " anchor")
    return text.replace(before, after, 1)


def plan() -> dict[str, bytes]:
    verified_checkout()
    original = {}
    for name in FILES:
        path = TARGET / name
        original[name] = path.read_bytes() if path.exists() else None

    # Publishing recovery: preserve first leading porcelain status column.
    p = original[GIT]
    if p is None:
        raise RuntimeError("Original private Git bridge missing")
    code = p.decode("utf8")
    fixed = (SOURCE / GIT).read_text("utf8")
    start = fixed.index("    # Do not use git(): it calls .strip()")
    end = fixed.index("    ready=[]", start)
    fragment = fixed[start:end]
    old = "    changes=git('status','--porcelain','--untracked-files=all','--','results')\n"
    if "changes=probe.stdout" in code:
        if fragment.strip() not in code:
            raise RuntimeError("Unexpected owner-modified Git recovery; preserve it")
    else:
        code = unique_replace(code, old, fragment, GIT)
    ast.parse(code, filename=GIT)
    outputs = {GIT: code.encode("utf8")}

    # Preserve each existing paired phone adapter; add ONLY a WSS-exclusive
    # verified status probe, never another network client or pairing store.
    p = original[PHONE]
    if p is None:
        raise RuntimeError("Original phone client missing")
    code = p.decode("utf8")
    fixed = (SOURCE / PHONE).read_text("utf8")
    start = fixed.index("def probe_native_wss_roundtrip(")
    end = fixed.index("def request(path:", start)
    fragment = fixed[start:end]
    if "def probe_native_wss_roundtrip(" in code:
        if fragment.strip() not in code:
            raise RuntimeError("Owner's WSS probe differs; refusing overwrite")
    else:
        if "_request_via_outbound_wss" not in code or "import time" not in code:
            raise RuntimeError("Original phone bridge is incompatible with WSS-only probe")
        code = unique_replace(code, "def request(path:", fragment + "def request(path:", PHONE)
    ast.parse(code, filename=PHONE)
    outputs[PHONE] = code.encode("utf8")

    # Keep every production-specific native route, change ONLY existing
    # Android bridge status endpoint and its import.
    p = original[ROUTES]
    if p is None:
        raise RuntimeError("Original Control native route missing")
    code = p.decode("utf8")
    import_anchor = "from .phone_bridge import PairPhone, PhoneInput, register, request, load"
    import_new = import_anchor + ", probe_native_wss_roundtrip"
    if import_new not in code:
        code = unique_replace(code, import_anchor, import_new, ROUTES)
    current = ("@router.get('/phone/bridge/status')\n"
               "def phone_bridge_status():\n"
               "    return request('/github-bridge/status').json()\n")
    changed = ("@router.get('/phone/bridge/status')\n"
               "def phone_bridge_status():\n"
               "    status = request('/github-bridge/status').json()\n"
               "    status['windows_native_roundtrip'] = probe_native_wss_roundtrip()\n"
               "    return status\n")
    if changed not in code:
        code = unique_replace(code, current, changed, ROUTES)
    ast.parse(code, filename=ROUTES)
    outputs[ROUTES] = code.encode("utf8")

    # Only update the exact reviewed original watchdog, not arbitrary owner
    # modifications to scheduled tasks or other service scripts.
    p = original[WATCHDOG]
    if p is None:
        raise RuntimeError("Original owner watchdog source missing")
    fixed = (SOURCE / WATCHDOG).read_bytes()
    source = fixed.decode("utf8")
    start = source.index("# R01: a native relay may report connected")
    end = source.index("# Native WSS recovery:", start)
    old = (source[:start] + source[end:]).encode("utf8")
    if p not in (fixed, old):
        raise RuntimeError("Unexpected original watchdog changes; safe manual reconciliation required")
    outputs[WATCHDOG] = fixed

    # No other relay instance or service is created. Guarded script is original-
    # path-specific, idle-only and requires an exact owner python.exe process.
    p = original[RELAY]
    desired = (SOURCE / RELAY).read_bytes()
    if p is not None and p != desired:
        raise RuntimeError("Existing owner reload helper differs; not replacing")
    outputs[RELAY] = desired
    for name in (GIT, PHONE, ROUTES):
        ast.parse(outputs[name].decode("utf8"), filename=name)
    for text, label in ((source, WATCHDOG), (desired.decode("utf8"), RELAY)):
        if "Remove-Item $key" in text or "mcp_gateway:app" in text:
            raise RuntimeError("Forbidden gateway or credential mutation in " + label)
    return outputs


def deploy(apply: bool) -> dict:
    payload = plan()
    changes = {}
    previous = {}
    for name in FILES:
        target = TARGET / name
        old = target.read_bytes() if target.exists() else None
        previous[name] = old
        changes[name] = {"changed": old != payload[name],
                         "source_sha256": digest(payload[name]),
                         "previous_sha256": digest(old) if old is not None else None}
    report = {"ok": True, "mode": "apply" if apply else "dry_run",
              "files": changes, "signer_changed": False,
              "pairing_changed": False, "service_restarted": False}
    if not apply:
        return report
    back = (Path(os.environ["LOCALAPPDATA"]) / "AsterionControl"
            / "deployment-backups" / "v6-m1-reliability")
    back.mkdir(parents=True, exist_ok=True)
    updated = []
    try:
        for name in FILES:
            dest = TARGET / name
            prior = previous[name]
            if prior is not None and prior != payload[name]:
                record = back / (name.replace("/", "__") + "-" + digest(prior) + ".bak")
                try:
                    with record.open("xb") as output:
                        output.write(prior)
                        output.flush()
                        os.fsync(output.fileno())
                except FileExistsError:
                    if record.read_bytes() != prior:
                        raise RuntimeError("Immutable backup hash mismatch " + name)
        for name in FILES:
            dest = TARGET / name
            if previous[name] == payload[name]:
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            fd, temp = tempfile.mkstemp(prefix=".control-v6-", dir=dest.parent)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(payload[name])
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp, dest)
            finally:
                if os.path.exists(temp):
                    os.unlink(temp)
            updated.append(name)
            if digest(dest.read_bytes()) != digest(payload[name]):
                raise RuntimeError("After-write hash mismatch " + name)
    except BaseException:
        for name in reversed(updated):
            target = TARGET / name
            before = previous[name]
            if before is None:
                target.unlink(missing_ok=True)
            else:
                target.write_bytes(before)
        raise
    report["deployed_files"] = updated
    report["backup_dir"] = str(back)
    report["service_restarted"] = False
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    options = parser.parse_args()
    print(json.dumps(deploy(options.apply), sort_keys=True, separators=(",", ":")), flush=True)
