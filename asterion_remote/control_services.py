"""Asterion Control internal APIs: deterministic script execution and observed health only.
No AI, model inference, autonomous policy or learning in this module.
"""
from __future__ import annotations
import os, platform, re, time
from pathlib import Path
from fastapi import HTTPException
from pydantic import BaseModel, Field

SCRIPT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
SCRIPT_ROOT = Path(os.getenv("ASTERION_CONTROL_SCRIPTS", str(Path.home() / ".asterion-control" / "scripts"))).expanduser()
SUFFIXES = {".py",".ps1",".cmd",".bat",".sh"}

class ScriptRun(BaseModel):
    script_id: str = Field(min_length=1,max_length=80)
    arguments: list[str] = Field(default_factory=list,max_length=32)
    cwd: str = "."

class BatchRequest(BaseModel):
    jobs: list[ScriptRun] = Field(min_length=1,max_length=16)
    mode: str = Field(default="parallel",pattern="^(parallel|sequential)$")

def safe_script(script_id: str) -> Path:
    if not SCRIPT_ID.fullmatch(script_id):
        raise HTTPException(422,"Invalid script ID")
    base = SCRIPT_ROOT.resolve()
    matches = [ext for ext in SUFFIXES if (base / (script_id + ext)).is_file()]
    if len(matches) != 1:
        raise HTTPException(404,"Script not found or ambiguous")
    path = (base / (script_id + matches[0])).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise HTTPException(403,"Script outside authorized library")
    return path

def script_command(script_id: str,args: list[str]) -> list[str]:
    path = safe_script(script_id)
    if len(args)>32 or any(len(arg)>4096 or "\0" in arg for arg in args):
        raise HTTPException(422,"Invalid script arguments")
    if path.suffix == ".py":
        return [os.getenv("ASTERION_PYTHON","python"),str(path),*args]
    if path.suffix == ".ps1":
        if os.name != "nt":
            raise HTTPException(503,"PowerShell scripts require Windows")
        return ["powershell.exe","-NoProfile","-NonInteractive","-File",str(path),*args]
    if path.suffix in (".cmd",".bat"):
        if os.name != "nt":
            raise HTTPException(503,"Windows batch scripts require Windows")
        if any(re.search(r'[&|<>^%!"\r\n]', arg) for arg in args):
            raise HTTPException(422,"Unsafe batch-script argument")
        return ["cmd.exe","/d","/s","/c",str(path),*args]
    if path.suffix == ".sh":
        return ["sh",str(path),*args]
    raise HTTPException(422,"Unsupported script type")

def script_list() -> list[dict]:
    if not SCRIPT_ROOT.is_dir():
        return []
    return [{"id":p.stem,"kind":p.suffix[1:],"bytes":p.stat().st_size}
      for p in sorted(SCRIPT_ROOT.iterdir()) if p.is_file() and p.suffix.lower() in SUFFIXES and SCRIPT_ID.fullmatch(p.stem)]

def thermal_info() -> dict:
    data = {"available":False,"sensors":[],"thermal_pressure":"unknown"}
    try:
        import psutil
        fn = getattr(psutil,"sensors_temperatures",None)
        for group,rows in (fn() if callable(fn) else {}).items():
            for sensor in rows:
                data["sensors"].append({"group":group,"label":sensor.label or group,
                  "celsius":sensor.current,"high":sensor.high,"critical":sensor.critical})
        data["available"] = bool(data["sensors"])
    except (ImportError,OSError,RuntimeError):
        pass
    return data

def host_health() -> dict:
    try:
        import psutil
    except ImportError as exc:
        raise HTTPException(503,"psutil required for health endpoint") from exc
    try:
        battery = psutil.sensors_battery()
    except (OSError,NotImplementedError):
        battery = None
    disks = []
    for partition in psutil.disk_partitions(all=False):
        try:
            disk = psutil.disk_usage(partition.mountpoint)
            disks.append({"mount":partition.mountpoint,"free":disk.free,"total":disk.total,
                          "percent_used":disk.percent})
        except (OSError,PermissionError):
            continue
    net = psutil.net_io_counters()
    return {"host":platform.node(),"os":platform.platform(),"sampled_at":time.time(),
      "cpu_percent":psutil.cpu_percent(interval=None),
      "memory":psutil.virtual_memory()._asdict(),"swap":psutil.swap_memory()._asdict(),
      "disks":disks,"network":{"bytes_sent":net.bytes_sent,"bytes_recv":net.bytes_recv} if net else None,
      "battery":{"percent":battery.percent,"plugged":battery.power_plugged,
                 "seconds_left":battery.secsleft} if battery else None,
      "thermals":thermal_info(),"gpu":{"available":False,"reason":"No supported GPU telemetry provider installed"}}
