"""Read-only verification against the running production Windows Control port.

Tests fresh UI state and rejection of an invalid token. It never makes a
successful phone input, requests screenshots, or changes installed apps.
"""
import asyncio
import json
import os
import time
from pathlib import Path
from websockets.asyncio.client import connect

STATE=Path(os.environ.get("LOCALAPPDATA",str(Path.home())))/"AsterionControl"
URL=os.environ.get("ASTERION_VERIFY_LIVE_URL",
                   "ws://192.168.1.133:8911/api/v1/stream/phone")


async def main():
    token=(STATE/"control-token.txt").read_text("utf-8").strip()
    start=time.perf_counter()
    async with connect(URL,origin="http://"+URL.split("/")[2],
                       open_timeout=5,close_timeout=2,max_size=2_000_000) as ws:
        await ws.send(json.dumps({"token":token,"video":False,"fps":1}))
        await ws.send(json.dumps({"type":"inspect","id":"deploy-inspect-1"}))
        first=json.loads(await asyncio.wait_for(ws.recv(),timeout=6))
        if first.get("type")!="ui_state" or not first.get("ok"):
            raise RuntimeError("Deployed server cannot inspect Android accessibility state")
        if not first.get("state_id") or not first.get("state",{}).get("available"):
            raise RuntimeError("Deployed server lacks one-use Android state tokens")

        await ws.send(json.dumps({"type":"input","id":"deploy-deny-1",
                                  "state_id":"intentionally-unrecognized-token",
                                  "payload":{"action":"back"}}))
        denied=json.loads(await asyncio.wait_for(ws.recv(),timeout=6))
        if denied.get("type")!="input_ack" or denied.get("ok") is not False:
            raise RuntimeError("Deployed server did not reject invalid state token")
        await ws.send(json.dumps({"type":"inspect","id":"deploy-inspect-2"}))
        second=json.loads(await asyncio.wait_for(ws.recv(),timeout=6))
        if second.get("type")!="ui_state" or not second.get("ok"):
            raise RuntimeError("Deployed server cannot re-inspect after rejection")

    print("DEPLOYED_LIVE_CONTROL "+json.dumps({
        "status":"passed","semantic_inspect":True,
        "state_token_present":True,"invalid_action_rejected":True,
        "state_reinspect":True,"actual_phone_input_executed":False,
        "screenshot_capture_requested":False,
        "roundtrip_total_ms":round((time.perf_counter()-start)*1000,1),
    },separators=(",",":")),flush=True)


if __name__=="__main__":
    asyncio.run(main())
