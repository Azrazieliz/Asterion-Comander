"""Restore ChatGPT through the existing Control native /apps/launch route.

Run only during owner-approved app-switch acceptance. Does not send a chat message,
alter permissions, clear app data, or approve Android MediaProjection consent.
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, r"D:\AsterionControlRelease")
import httpx
from asterion_remote.phone_bridge import request

root = Path(os.environ["LOCALAPPDATA"]) / "AsterionControl"
base = (root / "agent-host.txt").read_text(encoding="utf-8").strip()
token = (root / "control-token.txt").read_text(encoding="utf-8").strip()
client = httpx.Client(base_url=base, headers={"Authorization": "Bearer " + token}, timeout=4, trust_env=False)
events = []

def foreground():
    response = client.get("/api/v1/phone/ui")
    response.raise_for_status()
    return response.json().get("foreground_package")

def launch(package):
    start = time.perf_counter()
    reply = request("/apps/launch", "POST", {"package": package}, timeout=6).json()
    events.append({"launch": package, "reply": reply, "duration_ms": round((time.perf_counter()-start)*1000, 1)})
    if not reply.get("intent_dispatched"):
        raise RuntimeError("APP_LAUNCH_REJECTED:" + package)
    until = time.monotonic() + 7
    while time.monotonic() < until:
        if foreground() == package:
            events.append({"verified_foreground": package})
            return
        time.sleep(.2)
    raise RuntimeError("FOREGROUND_VERIFICATION_FAILED:" + package)

try:
    before = foreground()
    events.append({"before": before})
    if before != "com.asterion.control":
        launch("com.asterion.control")
    if foreground() != "com.asterion.control":
        raise RuntimeError("CONTROL_NOT_FOREGROUND")
    launch("com.openai.chatgpt")
    after = foreground()
    print(json.dumps({"ok": after == "com.openai.chatgpt", "after": after, "events": events}, ensure_ascii=False))
except Exception as exc:
    print(json.dumps({"ok": False, "error": str(exc), "events": events}, ensure_ascii=False))
    raise
