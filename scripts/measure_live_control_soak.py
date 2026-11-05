"""Sustained Asterion Control-only Samsung video/input latency test.

Uses the existing authenticated private WebSocket, no ADB/GitHub in test data path.
Writes only aggregate metadata (never frame contents, secrets or UI text).
"""
from __future__ import annotations
import asyncio
import hashlib
import json
import os
import statistics
import time
from collections import Counter
from pathlib import Path
from websockets.asyncio.client import connect

STATE=Path(os.environ.get("LOCALAPPDATA",str(Path.home())))/"AsterionControl"
SECRET=(STATE/"control-token.txt").read_text(encoding="utf-8").strip()
URL="ws://192.168.1.133:8911/api/v1/stream/phone"
DURATION=90.0
FPS=18

def metric(x):
    if not x: return None
    s=sorted(x)
    return {"min":round(s[0],1),"median":round(statistics.median(s),1),
            "p95":round(s[min(len(s)-1,int(.95*(len(s)-1)))],1),
            "p99":round(s[min(len(s)-1,int(.99*(len(s)-1)))],1),
            "max":round(s[-1],1)}

async def main():
    print("SOAK_BEGIN duration_s=90 fps_requested=18",flush=True)
    begin=time.perf_counter()
    samples=[]
    sizes=[]
    digests=set()
    errors=[]
    acks=[]
    pending={}
    control_sent=0
    frames_per_quarter=[0,0,0,0]
    first=None
    last_report=begin
    async with connect(URL,origin="http://192.168.1.133:8911",
                       max_size=4200000,open_timeout=8,close_timeout=3,
                       ping_interval=15,ping_timeout=8) as ws:
        await ws.send(json.dumps({"token":SECRET,"monitor":1,"fps":FPS}))
        while (now:=time.perf_counter())-begin<DURATION:
            elapsed=now-begin
            # Two user-authorized harmless navigation gestures during live stream.
            # App UI text / screen contents are not inspected or recorded.
            for stage,when,payload in [
              ("home",10,{"action":"home"}),
              ("swipe",55,{"action":"swipe","x":850,"y":1150,"x2":240,"y2":1150,"duration_ms":400})
            ]:
                if elapsed>=when and stage not in pending:
                    pending[stage]=time.perf_counter()
                    await ws.send(json.dumps({"type":"input","id":stage,"payload":payload}))
                    control_sent+=1
            try:msg=await asyncio.wait_for(ws.recv(),timeout=5)
            except asyncio.TimeoutError:
                errors.append("frame_stream_timeout")
                continue
            except Exception as e:
                errors.append(type(e).__name__+":"+str(e)[:100]);break
            now=time.perf_counter()
            if isinstance(msg,bytes):
                if first is None:first=now
                samples.append(now)
                sizes.append(len(msg))
                digests.add(hashlib.sha256(msg).digest())
                bucket=min(3,int((now-begin)/(DURATION/4)))
                frames_per_quarter[bucket]+=1
            else:
                try:status=json.loads(msg)
                except ValueError:
                    errors.append("invalid_control_json");continue
                typ=status.get("type","")
                if typ=="input_ack":
                    name=status.get("id")
                    if name in pending:
                        acks.append({"name":name,"ok":status.get("ok"),
                             "rtt_ms":round((now-pending[name])*1000,1),
                             "device_ms":status.get("device_ms"),
                             "error":status.get("error")})
                elif typ=="error":
                    errors.append(str(status.get("error"))[:120])
            if now-last_report>=30:
                print(f"SOAK_PROGRESS seconds={int(now-begin)} frames={len(samples)} errors={len(errors)}",flush=True)
                last_report=now
    intervals=[(b-a)*1000 for a,b in zip(samples,samples[1:])]
    actual_duration=(samples[-1]-samples[0]) if len(samples)>1 else 0
    print(json.dumps({
        "transport":"authenticated native Android 18fps Wi-Fi WebSocket; no GitHub/ADB/Work",
        "duration_requested_s":DURATION,
        "elapsed_s":round(time.perf_counter()-begin,2),
        "frames":len(samples),
        "unique_payloads":len(digests),
        "delivered_fps":round((len(samples)-1)/actual_duration,2) if actual_duration>0 else 0,
        "frames_each_22_5s":frames_per_quarter,
        "frame_interval_ms":metric(intervals),
        "frame_size_kb":metric([s/1024 for s in sizes]),
        "first_frame_ms":round((first-begin)*1000,1) if first else None,
        "actions_sent":control_sent,
        "input_acks":acks,
        "errors":errors,
    },separators=(",",":")),flush=True)

if __name__=="__main__":
    asyncio.run(main())
