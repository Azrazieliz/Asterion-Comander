"""Observed Control Windows app interaction, in a single persistent session.

Non-destructive: dismisses current Notepad error dialog and creates a new
unsaved tab, leaving existing open notes intact.
"""
from __future__ import annotations
import json,os,time
from pathlib import Path
import httpx
state=Path(os.environ.get("LOCALAPPDATA",str(Path.home()))) / "AsterionControl"
token=(state/"control-token.txt").read_text("utf-8").strip()
base="http://192.168.1.133:8911"
steps=[
 {"kind":"input","payload":{"action":"press","keys":["enter"]}},
 {"kind":"wait","wait_ms":250},
 {"kind":"input","payload":{"action":"hotkey","keys":["ctrl","n"]}},
 {"kind":"wait","wait_ms":650},
 {"kind":"input","payload":{"action":"type","text":"ASTERION CONTROL - WINDOWS APP DEMONSTRATION\nControlled from ChatGPT with one local multi-step session.\nNo GitHub round trip between keys."}},
 {"kind":"wait","wait_ms":350},
 {"kind":"capture","payload":{"monitor":1}},
 {"kind":"health"}
]
with httpx.Client(timeout=12,trust_env=False,follow_redirects=False,
                  headers={"Authorization":"Bearer "+token}) as c:
    start=time.perf_counter()
    r=c.post(base+"/api/v1/sessions",json={"device":"pc","steps":steps,
                              "stop_on_error":True,"timeout_s":45});r.raise_for_status()
    key=r.json()["id"]
    for _ in range(200):
        s=c.get(base+"/api/v1/sessions/"+key);s.raise_for_status();data=s.json()
        if data["state"] in ("completed","failed","timed_out","cancelled"):break
        time.sleep(.15)
    print(json.dumps({"state":data["state"],"steps_completed":data["current_step"],
        "total":data["steps_total"],"elapsed_ms":round((time.perf_counter()-start)*1000,1),
        "steps":[{"kind":x["kind"],"ok":x["ok"],
           "elapsed_ms":x["elapsed_ms"],
           "error":x.get("error")} for x in data["results"]],
        "capture_bytes":next((x["observation"]["bytes"] for x in data["results"]
                 if x["kind"]=="capture" and x["ok"]),None)},
        separators=(",",":")),flush=True)
    if data["state"]!="completed":raise RuntimeError("Windows visible-app session failed")
