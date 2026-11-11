"""Owner-authorized full-path Control recovery; no credential rotation or generic remote shell."""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from .security import require_token

router = APIRouter(prefix="/api/v1/recovery", dependencies=[Depends(require_token)])
ROOT = Path(__file__).resolve().parent.parent
STATE = Path(os.environ.get("ASTERION_CONTROL_STATE", str(Path.home()/".asterion-control")))
REPORT = STATE / "full-repair.json"
_lock = threading.Lock()

class RepairRequest(BaseModel):
    mode: str = "auto"

def _read():
    try:
        return json.loads(REPORT.read_text("utf-8"))
    except (OSError, ValueError, TypeError):
        return {"phase": "never_run", "ok": False, "steps": {}}

def _write(data):
    STATE.mkdir(parents=True, exist_ok=True)
    temp = REPORT.with_suffix(".incoming")
    temp.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    os.replace(temp, REPORT)

@router.get("/status")
def recovery_status():
    result = _read()
    if result.get("phase") == "running" and time.time()-result.get("updated", 0)>120:
        result = {**result, "phase": "stale", "ok": False,
                  "error": "Recovery process stopped without a final receipt"}
    return result

@router.post("/start", status_code=202)
def recovery_start(request: RepairRequest):
    if request.mode not in ("auto", "force"):
        raise HTTPException(422, "Mode must be auto or force")
    with _lock:
        previous = _read()
        if previous.get("phase") == "running" and time.time()-previous.get("updated", 0)<120:
            raise HTTPException(409, "Another Control recovery is running")
        script = ROOT/"scripts"/"control_full_repair.ps1"
        if not script.is_file():
            raise HTTPException(503, "Full-path repair script not installed on Windows worker")
        ticket = uuid.uuid4().hex
        _write({"id": ticket, "phase": "running", "mode": request.mode,
                "updated": time.time(), "steps": {}, "ok": False})
        args = ["powershell.exe", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-File", str(script),
                "-Mode", request.mode, "-RepairId", ticket]
        flags = (getattr(subprocess, "DETACHED_PROCESS", 0) |
                 getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)) if os.name == "nt" else 0
        try:
            subprocess.Popen(args, cwd=str(ROOT), stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=flags)
        except (OSError, ValueError) as exc:
            _write({"id":ticket, "phase":"failed", "updated":time.time(),
                    "ok":False, "error":type(exc).__name__, "steps":{}})
            raise HTTPException(503, "Could not start the Windows recovery process") from exc
        return {"id":ticket, "phase":"running", "ok":False, "mode":request.mode}
