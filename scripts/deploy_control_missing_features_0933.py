"""Additive, reversible deployment of source-tested Control services to the
existing owner-paired Windows agent.

Never changes the Android application, key material, worker, WSS relay or
watchdog. Default dry-run. Exact route/feature compatibility preconditions
must pass before a byte is replaced. A separate idle-only supervised reload
is required and reports its own verified outcome.
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
    "asterion_remote/native_routes.py",
    "asterion_remote/diagnostic_routes.py",
    "asterion_remote/control_v2_routes.py",
    "asterion_remote/control_ai_routes.py",
    "asterion_remote/overnight_supervisor.py",
    "asterion_remote/local_model_provider.py",
    "asterion_remote/security_scanner.py",
    "asterion_remote/skill_studio.py",
    "asterion_remote/vpn_route_policy.py",
    "asterion_remote/github_bridge.py",
)
MARKER_IMPORT = "from .diagnostic_routes import router as diagnostic_router"
MARKER_MOUNT = "app.include_router(diagnostic_router)"
EXTRA_IMPORTS = (
    "from .control_v2_routes import router as control_v2_router",
    "from .control_ai_routes import router as control_ai_router",
)
EXTRA_MOUNTS = (
    "app.include_router(control_v2_router)",
    "app.include_router(control_ai_router)",
)


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _routes(text: str) -> set[tuple[str, str]]:
    tree = ast.parse(text)
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for deco in node.decorator_list:
            if not isinstance(deco, ast.Call) or not isinstance(deco.func, ast.Attribute):
                continue
            if deco.func.attr not in {"get", "post", "put", "delete", "patch"}:
                continue
            if isinstance(deco.func.value, ast.Name) and deco.func.value.id == "router":
                if deco.args and isinstance(deco.args[0], ast.Constant):
                    found.add((deco.func.attr.upper(), deco.args[0].value))
    return found


def _patch_app(existing: str) -> str:
    if existing.count(MARKER_IMPORT) != 1 or existing.count(MARKER_MOUNT) != 1:
        raise RuntimeError("unexpected_owner_router_mount_structure")
    if any(line in existing for line in EXTRA_IMPORTS + EXTRA_MOUNTS):
        # This additive script is intentionally one-shot; do not overwrite a
        # newer installation merely because it already has functionality.
        if all(line in existing for line in EXTRA_IMPORTS + EXTRA_MOUNTS):
            return existing
        raise RuntimeError("partially_mounted_new_routes_reconcile_manually")
    updated = existing.replace(
        MARKER_IMPORT, MARKER_IMPORT + "\n" + "\n".join(EXTRA_IMPORTS), 1)
    updated = updated.replace(
        MARKER_MOUNT, MARKER_MOUNT + "\n" + "\n".join(EXTRA_MOUNTS), 1)
    ast.parse(updated, filename="asterion_remote/app.py")
    return updated


def preflight(source: Path, installed: Path) -> tuple[dict, dict[str, bytes]]:
    if installed.name.lower() != "asterioncontrolrelease":
        raise RuntimeError("wrong_production_installation")
    if source.resolve() == installed.resolve():
        raise RuntimeError("refusing_in_place_source_update")
    if not (source / ".git").is_dir():
        raise RuntimeError("must_run_from_existing_git_checkout")
    status = subprocess.run(
        ["git", "-C", str(source), "status", "--porcelain",
         "--untracked-files=no"], check=True, capture_output=True,
        text=True, timeout=15)
    if status.stdout.strip():
        raise RuntimeError("tested_source_has_uncommitted_changes")
    if not (installed / "asterion_remote" / "phone_bridge.py").is_file():
        raise RuntimeError("owner_pairing_adapter_missing")
    if not (installed / "asterion_remote" / "diagnostic_routes.py").is_file():
        raise RuntimeError("owner_diagnostics_not_installed")
    before = (installed / "asterion_remote" / "native_routes.py").read_text("utf8")
    after = (source / "asterion_remote" / "native_routes.py").read_text("utf8")
    removed = _routes(before) - _routes(after)
    if removed:
        raise RuntimeError("native_phone_routes_would_be_removed:" + repr(sorted(removed)))
    if ("phone/diagnostics/vpn" not in after or
            "/phone/cycles/status" not in after):
        raise RuntimeError("required_phone_routes_missing_in_candidate")
    if any("secret" in p.lower() for p in FILES):
        raise RuntimeError("unexpected_secret_path")
    patches = {}
    for rel in FILES:
        data = (source / rel).read_bytes()
        ast.parse(data.decode("utf8"), filename=rel)
        patches[rel] = data
    app_rel = "asterion_remote/app.py"
    original_app = (installed / app_rel).read_text("utf8")
    patches[app_rel] = _patch_app(original_app).encode("utf8")
    diffs = {}
    for path, data in patches.items():
        current = installed / path
        previous = current.read_bytes() if current.exists() else None
        diffs[path] = {
            "new_file": previous is None,
            "changed": previous != data,
            "old_sha256": _hash(previous) if previous is not None else None,
            "candidate_sha256": _hash(data),
        }
    return {
        "ok": True, "removed_routes": [],
        "added_native_routes": sorted(list(_routes(after) - _routes(before))),
        "files": diffs,
    }, patches


def deploy(source: Path, installed: Path, *, apply: bool = False) -> dict:
    result, patches = preflight(source, installed)
    result.update({
        "mode": "apply" if apply else "dry_run",
        "phone_data_changed": False,
        "pairing_changed": False,
        "service_restarted": False,
    })
    if not apply:
        return result
    backup = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / (
        "AsterionControl/deployment-backups/additive_features_0933")
    backup.mkdir(parents=True, exist_ok=True)
    previous: dict[str, bytes | None] = {}
    written: list[str] = []
    try:
        for relative in patches:
            current = installed / relative
            data = current.read_bytes() if current.exists() else None
            previous[relative] = data
            if data is not None:
                destination = backup / (relative.replace("/", "__") + "-" +
                                        _hash(data) + ".bak")
                try:
                    with destination.open("xb") as handle:
                        handle.write(data)
                        handle.flush()
                        os.fsync(handle.fileno())
                except FileExistsError:
                    if destination.read_bytes() != data:
                        raise RuntimeError("backup_hash_conflict")
        for relative, data in patches.items():
            if not result["files"][relative]["changed"]:
                continue
            current = installed / relative
            current.parent.mkdir(parents=True, exist_ok=True)
            fd, temp = tempfile.mkstemp(prefix=".asterion-features-",
                                         dir=current.parent)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp, current)
            finally:
                if os.path.exists(temp):
                    os.unlink(temp)
            written.append(relative)
            if _hash(current.read_bytes()) != _hash(data):
                raise RuntimeError("postwrite_checksum_failed:" + relative)
    except BaseException:
        for relative in reversed(written):
            current = installed / relative
            data = previous[relative]
            if data is None:
                current.unlink(missing_ok=True)
            else:
                current.write_bytes(data)
        raise
    result["installed_files"] = written
    result["backup_root"] = str(backup)
    return result


def main():
    arg = argparse.ArgumentParser()
    arg.add_argument("--apply", action="store_true")
    arg.add_argument("--production", default="D:/AsterionControlRelease")
    params = arg.parse_args()
    source = Path(__file__).resolve().parents[1]
    print(json.dumps(deploy(source, Path(params.production),
                            apply=params.apply), sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
