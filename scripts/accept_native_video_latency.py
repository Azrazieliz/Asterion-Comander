"""Local acceptance probe for Asterion native Windows-to-phone persistent WebSocket.
Read only by default. No frame bytes, pairing keys or screen contents are printed.
Use --tap X Y ONLY after verifying a safe target from current Accessibility UI.
"""
from __future__ import annotations
import argparse
import asyncio
import hashlib
import json
import os
import statistics
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from websockets.asyncio.client import connect

def percentile(values, pct):
    if not values:
        return None
    v=sorted(values)
    return round(v[min(len(v)-1,round((len(v)-1)*pct))], 1)

async def probe():
    ap=argparse.ArgumentParser()
    ap.add_argument("--frames",type=int,default=12)
    ap.add_argument("--tap",nargs=2,type=int,metavar=("X","Y"))
    args=ap.parse_args()
    root=Path(os.environ.get("LOCALAPPDATA",str(Path.home()))) / "AsterionControl"
    token=(root/"control-token.txt").read_text(encoding="utf-8").strip()
    base=(root/"agent-host.txt").read_text(encoding="utf-8").strip()
    p=urlparse(base)
    if not token or p.scheme!="http" or not p.port:
        raise RuntimeError("Saved private worker pairing unavailable")
    def status(path):
        rq=Request(base+path,headers={"Authorization":"Bearer "+token})
        with urlopen(rq,timeout=5) as response:
            return json.load(response)
    before=status("/api/v1/phone")
    if not before.get("reachable"):
        raise RuntimeError("Native phone listener offline")
    info=before.get("info",{})
    counters_before=info.get("performance",{}).get("frames_encoded",0)
    endpoint="ws://"+p.netloc+"/api/v1/stream/phone"
    frame_times=[]
    signatures=[]
    frame_sizes=[]
    actions=[]
    start=time.perf_counter()
    async with connect(endpoint,open_timeout=6,close_timeout=2,max_size=4_000_000) as ws:
        await ws.send(json.dumps({"token":token,"fps":12}))
        if args.tap:
            ident="video-latency-safe-tap-1"
            action_sent=False
        while len(frame_times)<args.frames:
            received=await asyncio.wait_for(ws.recv(),timeout=8)
            now=time.perf_counter()
            if isinstance(received,bytes):
                if not received.startswith(b"\xff\xd8") or not received.endswith(b"\xff\xd9"):
                    raise RuntimeError("Video frame is not valid JPEG")
                frame_times.append(now)
                frame_sizes.append(len(received))
                signatures.append(hashlib.sha256(received).hexdigest()[:12])
                if args.tap and not action_sent:
                    sent=time.perf_counter()
                    await ws.send(json.dumps({"type":"input","id":ident,
                        "payload":{"action":"tap","x":args.tap[0],"y":args.tap[1]}}))
                    action_sent=True
            else:
                try:
                    event=json.loads(received)
                except (TypeError,ValueError):
                    event={"type":"invalid_json"}
                if event.get("type")=="input_ack" and args.tap:
                    actions.append({"ok":event.get("ok",False),
                        "roundtrip_ms":round((now-sent)*1000,1),
                        "device_ms":event.get("device_ms"),
                        "error":event.get("error")})
    after=status("/api/v1/phone")
    counters_after=after.get("info",{}).get("performance",{}).get("frames_encoded",0)
    ui=status("/api/v1/phone/ui")
    gaps=[(frame_times[i]-frame_times[i-1])*1000 for i in range(1,len(frame_times))]
    print(json.dumps({
        "stream":"direct_worker_to_android_native_mjpeg",
        "connected":True,
        "frames_received":len(frame_times),
        "first_frame_ms":round((frame_times[0]-start)*1000,1) if frame_times else None,
        "frame_gap_median_ms":percentile(gaps,0.5),
        "frame_gap_p95_ms":percentile(gaps,0.95),
        "duration_ms":round((frame_times[-1]-start)*1000,1),
        "frame_sizes_min_max":[min(frame_sizes),max(frame_sizes)],
        "distinct_frame_payloads":len(set(signatures)),
        "device_encoded_delta":counters_after-counters_before,
        "native_capture":after.get("info",{}).get("capture"),
        "foreground":ui.get("foreground_package"),
        "actions":actions
    },separators=(",",":")))
if __name__=="__main__":
    asyncio.run(probe())
