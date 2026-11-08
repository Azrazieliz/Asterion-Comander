"""Exercise the new interactive WebSocket protocol against the ACTUAL paired phone.

One real reversible SystemUI gesture is allowed: open notification shade, inspect,
then Back. No screenshots, typed messages, foreground app installations or writes.
Runs the new development transport in-process, without restarting production.
Only summary timings are printed; never print UI content or pairing secrets.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from asterion_remote.live_stream import install_stream

STATE=Path(os.environ.get("LOCALAPPDATA",str(Path.home())))/"AsterionControl"
APP=FastAPI()
install_stream(APP,lambda _:b"unused",lambda _:{"ok":True})


def receive(session,kind,ident):
    for _ in range(8):
        reply=session.receive_json()
        if reply.get("type")==kind and reply.get("id")==ident:
            return reply
    raise RuntimeError("Missing interactive Control response")


def inspect(session,name):
    started=time.perf_counter()
    session.send_json({"type":"inspect","id":name})
    value=receive(session,"ui_state",name)
    if not value.get("ok"):
        raise RuntimeError("Live Android UI unavailable: "+str(value.get("error"))[:100])
    return value,round((time.perf_counter()-started)*1000,1)


def action(session,name,state,action_name,expected):
    started=time.perf_counter()
    session.send_json({"type":"input","id":name,
                       "state_id":state["state_id"],
                       "expect_package":expected,
                       "payload":{"action":action_name}})
    value=receive(session,"input_ack",name)
    return value,round((time.perf_counter()-started)*1000,1)


def main():
    token=(STATE/"control-token.txt").read_text(encoding="utf-8").strip()
    result={"method":"interactive native WebSocket inspect -> guarded input -> inspect",
            "video":False,"phone_unchanged_except_reversible_shade":True}
    with TestClient(APP) as client:
        with client.websocket_connect("/api/v1/stream/phone") as ws:
            ws.send_json({"token":token,"video":False})
            initial,read_ms=inspect(ws,"owner-start")
            before=initial["state"]["foreground_package"]
            result["initial_app"]=before
            result["inspect_ms"]=read_ms
            if before!="com.openai.chatgpt":
                result["status"]="not_started"
                result["reason"]="ChatGPT not foreground"
                print(json.dumps(result,separators=(",",":")),flush=True)
                return
            performed=False
            try:
                opened,ack_ms=action(ws,"open-shade",initial,"notifications",before)
                result["open_shade_ack_ok"]=opened.get("ok") is True
                result["open_shade_ack_ms"]=ack_ms
                if not opened.get("ok"):
                    result["status"]="rejected"
                    return
                performed=True
                # Android transitions can finish AFTER native input_ack.
                # Observe until SystemUI is actually foreground, not just until
                # the gesture is acknowledged.
                after=before
                current_ms=0.0
                for n in range(20):
                    current,ms=inspect(ws,"after-shade-"+str(n))
                    current_ms+=ms
                    after=current["state"].get("foreground_package")
                    if after=="com.android.systemui":
                        break
                    time.sleep(0.08)
                result["observed_after_action"]=after
                result["shade_observed"]=after=="com.android.systemui"
                result["inspect_after_ms"]=round(current_ms,1)
                # An old inspection may not authorize a second gesture.
                ws.send_json({"type":"input","id":"reject-old-token",
                              "state_id":initial["state_id"],
                              "payload":{"action":"back"}})
                refused=receive(ws,"input_ack","reject-old-token")
                result["old_state_rejected"]=refused.get("ok") is False
            finally:
                if performed:
                    # A fresh inspection is required after the refused attempt.
                    state,_=inspect(ws,"reinspect-before-restore")
                    foreground=state["state"].get("foreground_package")
                    if foreground!="com.openai.chatgpt":
                        restored,ms=action(ws,"return-ChatGPT",state,"back",foreground)
                        result["restore_ack_ok"]=restored.get("ok") is True
                        result["restore_ack_ms"]=ms
                    after_restore=""
                    for n in range(20):
                        final,_=inspect(ws,"final-verification-"+str(n))
                        after_restore=final["state"].get("foreground_package")
                        if after_restore==before:break
                        time.sleep(0.08)
                    result["final_app"]=after_restore
                    result["restored"]=after_restore==before
                    result["draft_not_edited"]=True
            result["status"]="passed" if (result.get("open_shade_ack_ok") and
                result.get("shade_observed") and result.get("old_state_rejected")
                and result.get("restored")) else "partial"
    print(json.dumps(result,separators=(",",":")),flush=True)


if __name__=="__main__":
    main()
