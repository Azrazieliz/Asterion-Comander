"""Actual owner Windows -> Android two-step M2 session acceptance.

Uses the existing authenticated Control API; never launches apps, taps, captures
screens, sends messages or prints credentials. Fails closed if the live status
or durable repeat-request receipt is not real. No new transport is created.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx

REQUEST_ID = "control-v6-m2-20261119-native-health-2steps-0001"
TERMINAL = {"completed","failed","cancelled","timed_out","outcome_unknown"}

def main():
    state=Path(os.environ["LOCALAPPDATA"])/"AsterionControl"
    base=(state/"agent-host.txt").read_text("utf8").strip()
    token=(state/"control-token.txt").read_text("utf8").strip()
    if not base.startswith("http://") or len(token)<32:
        raise RuntimeError("Original Control API pairing unavailable")
    payload={
      "device":"phone","steps":[{"kind":"health"},{"kind":"health"}],
      "timeout_s":45,"request_id":REQUEST_ID,
    }
    result={"ok":False,"test":"native_m2_two_step_health",
            "wss_roundtrip_preflight":False,"session_completed":False,
            "steps_verified":0,"duplicate_request_replayed":None}
    with httpx.Client(base_url=base,trust_env=False,timeout=10,
                     headers={"Authorization":"Bearer "+token},
                     follow_redirects=False) as client:
        before=client.get("/api/v1/phone/bridge/status")
        before.raise_for_status()
        native=before.json().get("windows_native_roundtrip")
        if not isinstance(native,dict) or not native.get("verified") or native.get("transport")!="native_wss":
            result["failure"]="fresh_native_wss_unavailable"
            return result
        result["wss_roundtrip_preflight"]=True
        result["network"]=native.get("network")
        first=client.post("/api/v1/sessions",json=payload)
        first.raise_for_status()
        created=first.json()
        if not isinstance(created.get("id"),str):
            raise RuntimeError("No genuine persistent session identifier")
        deadline=time.monotonic()+48
        final=None
        while time.monotonic()<deadline:
            status=client.get("/api/v1/sessions/"+created["id"])
            status.raise_for_status()
            final=status.json()
            if final.get("state") in TERMINAL:
                break
            time.sleep(.5)
        if not final or final.get("state") not in TERMINAL:
            result["failure"]="real_session_did_not_finish"
            return result
        result["session_state"]=final["state"]
        raw=final.get("results",[])
        rows=raw if isinstance(raw,list) else []
        result["steps_verified"]=sum(bool(x.get("ok")) and x.get("kind")=="health" and
             x.get("device")=="phone" and bool((x.get("observation") or {}).get("ok"))
             for x in rows)
        result["session_completed"]=final["state"]=="completed" and result["steps_verified"]==2
        duplicate=client.post("/api/v1/sessions",json=payload)
        duplicate.raise_for_status()
        dupe=duplicate.json()
        result["duplicate_request_replayed"]=not (
            dupe.get("reused") is True and dupe.get("replay_allowed") is False and
            dupe.get("id")==created["id"])
        result["ok"]=(result["wss_roundtrip_preflight"] and
                      result["session_completed"] and
                      result["duplicate_request_replayed"] is False)
        return result

if __name__=="__main__":
    verdict=main()
    print(json.dumps(verdict,sort_keys=True,separators=(",",":")),flush=True)
    raise SystemExit(0 if verdict["ok"] else 2)
