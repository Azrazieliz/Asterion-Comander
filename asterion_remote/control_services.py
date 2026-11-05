"""Asterion Control internal automation and device-health helpers.

No AI, no autonomous planning: only explicitly defined scripts and native telemetry.
This module is deliberately independent of Asterion's other application engines.
"""
from __future__ import annotations

import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import time
from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel, Field

SCRIPT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
SCRIPT_ROOT = Path(os.getenv("ASTERION_CONTROL_SCRIPTS", str(Path.home() / ".asterion-control" / "scripts"))).expanduser()
SUFFIXES = {".py", ".ps1", ".cmd", ".bat", ".sh"}


class ScriptRun(BaseModel):
    script_id: str = Field(min_length=1, max_length=80)
    arguments: list[str] = Field(default_factory=list, max_length=32)
    cwd: str = "."


class BatchRequest(BaseModel):
    jobs: list[ScriptRun] = Field(min_length=1, max_length=16)
    mode: str = Field(default="parallel", pattern="^(parallel|sequential)$")


def safe_script(script_id: str) -> Path:
    if not SCRIPT_ID.fullmatch(script_id):
        raise HTTPException(422, "Invalid script ID")
    base = SCRIPT_ROOT.resolve()
    matches = [x for x in SUFFIXES if (base / (script_id + x)).is_file()]
    if len(matches) != 1:
        raise HTTPException(404, "Script not found or ambiguous")
    result = (base / (script_id + matches[0])).resolve()
    if not result.is_relative_to(base) or not result.is_file():
        raise HTTPException(403, "Script outside authorized library")
    return result


def script_command(script_id: str, args: list[str]) -> list[str]:
    p = safe_script(script_id)
    if len(args) > 32 or any(len(a) > 4096 or '\x00' in a for a in args):
        raise HTTPException(422, "Invalid script arguments")
    if p.suffix == ".py":
        return [os.getenv("ASTERION_PYTHON", "python"), str(p), *args]
    if p.suffix == ".ps1":
        if os.name != "nt":
            raise HTTPException(503, "PowerShell scripts require Windows in this build")
        return ["powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(p), *args]
    if p.suffix in (".cmd", ".bat"):
        if os.name != "nt":
            raise HTTPException(503, "Windows batch scripts require Windows")
        # cmd.exe sees raw tokens; reject control metacharacters for batch files.
        if any(re.search(r'[&|<>^%!"\r\n]', value) for value in args):
            raise HTTPException(422, "Unsafe batch-script argument")
        return ["cmd.exe", "/d", "/s", "/c", str(p), *args]
    if p.suffix == ".sh":
        return ["sh", str(p), *args]
    raise HTTPException(422, "Unsupported script type")


def script_list() -> list[dict]:
    if not SCRIPT_ROOT.is_dir():
        return []
    result = []
    for p in sorted(SCRIPT_ROOT.iterdir()):
        if p.is_file() and p.suffix.lower() in SUFFIXES and SCRIPT_ID.fullmatch(p.stem):
            result.append({"id": p.stem, "kind": p.suffix[1:], "bytes": p.stat().st_size})
    return result


def thermal_info() -> dict:
    """Measured OS-exposed sensors only; do not invent thermal values."""
    data = {"available": False, "sensors": [], "thermal_pressure": "unknown"}
    try:
        import psutil
        fn = getattr(psutil, "sensors_temperatures", None)
        temperatures = fn() if callable(fn) else {}
        for group, rows in temperatures.items():
            for sensor in rows:
                data["sensors"].append({"group": group, "label": sensor.label or group,
                    "celsius": sensor.current, "high": sensor.high,
                    "critical": sensor.critical})
        data["available"] = bool(data["sensors"])
    except (ImportError, OSError, RuntimeError):
        pass
    # No arbitrary 'temperature' derived from CPU load. Windows may have no readable sensors.
    return data


def host_health() -> dict:
    try:
        import psutil
    except ImportError as exc:
        raise HTTPException(503, "psutil required for health endpoint") from exc
    try:
        battery = psutil.sensors_battery()
    except (OSError, NotImplementedError):
        battery = None
    disk = []
    for partition in psutil.disk_partitions(all=False):
        try:
            d = psutil.disk_usage(partition.mountpoint)
            disk.append({"mount": partition.mountpoint, "free": d.free, "total": d.total, "percent_used": d.percent})
        except (OSError, PermissionError):
            continue
    net = psutil.net_io_counters()
    return {"host": platform.node(), "os": platform.platform(),
        "sampled_at": time.time(), "cpu_percent": psutil.cpu_percent(interval=None),
        "memory": psutil.virtual_memory()._asdict(), "swap": psutil.swap_memory()._asdict(),
        "disks": disk,
        "network": {"bytes_sent": net.bytes_sent, "bytes_recv": net.bytes_recv} if net else None,
        "battery": ({"percent": battery.percent, "plugged": battery.power_plugged,
                    "seconds_left": battery.secsleft} if battery else None),
        "thermals": thermal_info(),
        "gpu": {"available": False, "reason": "No supported GPU telemetry provider installed"}}
