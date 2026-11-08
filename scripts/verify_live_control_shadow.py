"""Non-disruptive isolated deployment check for state-aware native Control.

Starts development Control server only on local loopback port 8912, reads
real phone UI and verifies rejection of an expired state token. Never sends an
actual Android input. Stops shadow server before exit; no capture requested.
"""
from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from websockets.asyncio.client import connect

ROOT=Path(__file__).resolve().parents[1]
PYTHON=sys.executable
STATE=Path(os.environ.get("LOCALAPPDATA",str(Path.home())))/"AsterionControl"
HOST="127.0.0.1"
PORT=8912
URL=f"ws://{HOST}:{PORT}/api/v1/stream/phone"


async def inspect():
    token=(STATE/"control-token.txt").read_text("utf-8").strip()
    started=time.perf_counter()
    async with connect(URL,origin=f"http://{HOST}:{PORT}",open_timeout=5,
                       close_timeout=2,max_size=1_000_000) as stream:
        await stream.send(json.dumps({"token":token,"video":False,"fps":1}))
        await stream.send(json.dumps({"type":"inspect","id":"shadow-read"}))
        observation=json.loads(await asyncio.wait_for(stream.recv(),timeout=8))
        if not observation.get("ok") or observation.get("type")!="ui_state":
            raise RuntimeError("Shadow native UI read failed")
        foreground=observation["state"].get("foreground_package")
        await stream.send(json.dumps({
            "type":"input","id":"shadow-reject",
            "state_id":"deliberately-invalid-token",
            "expect_package":foreground,
            "payload":{"action":"back"},
        }))
        refusal=json.loads(await asyncio.wait_for(stream.recv(),timeout=5))
        if refusal.get("ok") is not False:
            raise RuntimeError("Shadow server did not reject an invalid state")
    return {"status":"passed","method":"state_guarded_direct_WebSocket",
            "phone_ui_available":bool(foreground),
            "stale_action_rejected":True,
            "no_phone_input_executed":True,
            "loopback_only":True,
            "end_to_end_elapsed_ms":round((time.perf_counter()-started)*1000,1)}


def main():
    launch=[PYTHON,"-m","uvicorn","asterion_remote.app:app",
            "--host",HOST,"--port",str(PORT),"--log-level","error"]
    flags=getattr(subprocess,"CREATE_NO_WINDOW",0)
    proc=subprocess.Popen(launch,cwd=str(ROOT),stdin=subprocess.DEVNULL,
                          stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                          creationflags=flags)
    try:
        deadline=time.monotonic()+15
        ready=False
        while time.monotonic()<deadline and proc.poll() is None:
            try:
                with socket.create_connection((HOST,PORT),timeout=.3):
                    ready=True;break
            except OSError:
                time.sleep(.13)
        if not ready:
            raise RuntimeError("Isolated Control server did not reach ready state")
        print("SHADOW_LIVE_CONTROL "+json.dumps(asyncio.run(inspect()),
              separators=(",",":")),flush=True)
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=2)

if __name__=="__main__":
    main()
