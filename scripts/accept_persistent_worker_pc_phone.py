"""Acceptance: ONE persistent Windows worker controlling both Windows desktop and Android.

The same live authenticated worker keeps two WebSocket streams active while inputs
alternate PC -> phone -> PC -> phone -> PC -> phone. Does not send chat messages.
PC mouse movement is restored. Phone navigation is non-destructive.
Only event metrics and status are printed, never credentials or screenshots.
"""
from __future__ import annotations
import asyncio
import ctypes
import json
import os
import statistics
import time
from ctypes import wintypes
from pathlib import Path
from urllib.parse import urlsplit
import httpx
from websockets.asyncio.client import connect

STATE = Path(os.environ["LOCALAPPDATA"]) / "AsterionControl"

class Point(ctypes.Structure):
    _fields_=[("x",ctypes.c_long),("y",ctypes.c_long)]

def cursor():
    p=Point()
    if not ctypes.windll.user32.GetCursorPos(ctypes.byref(p)):
        raise RuntimeError("PC_CURSOR_UNREADABLE")
    return (p.x,p.y)

def pct(values):
    if not values:return None
    return round(statistics.median(values),1)

async def main():
    token=(STATE / "control-token.txt").read_text(encoding="utf-8").strip()
    base=(STATE / "agent-host.txt").read_text(encoding="utf-8").strip()
    url=urlsplit(base)
    if url.scheme!="http" or url.port!=8911:
        raise RuntimeError("Existing private worker endpoint missing")
    headers={"Authorization":"Bearer "+token}
    records=[]
    async with httpx.AsyncClient(base_url=base,headers=headers,trust_env=False,timeout=5.0,
                                 limits=httpx.Limits(max_connections=4,max_keepalive_connections=4)) as client:
        health=(await client.get("/api/v1/health")).json()
        if not health.get("ok"):raise RuntimeError("WORKER_NOT_HEALTHY")
        status=(await client.get("/api/v1/phone")).json()
        if not (status.get("paired") and status.get("reachable")):
            raise RuntimeError("PHONE_NOT_REACHABLE")
        monitors=(await client.get("/api/v1/monitors")).json().get("items",[])
        if not monitors:raise RuntimeError("PC_MONITORS_UNAVAILABLE")
        before=(await client.get("/api/v1/phone/ui")).json().get("foreground_package")
        original=cursor()
        selected=None
        for m in monitors:
            if m.get("index",0)==0:continue
            if (m["left"]<=original[0]<m["left"]+m["width"] and
                m["top"]<=original[1]<m["top"]+m["height"]):
                selected=m;break
        if selected is None:
            selected=next(m for m in monitors if m.get("index")==1)
        x=min(max(original[0]-selected["left"],20),selected["width"]-30)
        y=min(max(original[1]-selected["top"],20),selected["height"]-30)
        newx=min(selected["width"]-18,x+12)
        newy=min(selected["height"]-18,y+9)
        wsbase="ws://"+url.netloc+"/api/v1/stream/"
        start=time.perf_counter()
        async with connect(wsbase+"desktop",max_size=4_000_000,open_timeout=7,
                           close_timeout=2,ping_interval=20) as pc, connect(
                           wsbase+"phone",max_size=4_000_000,open_timeout=7,
                           close_timeout=2,ping_interval=20) as phone:
            await asyncio.gather(
                pc.send(json.dumps({"token":token,"fps":7})),
                phone.send(json.dumps({"token":token,"fps":7})))
            frames={"pc":0,"phone":0}
            async def get_ack(ws,target,which):
                while True:
                    item=await asyncio.wait_for(ws.recv(),timeout=6)
                    if isinstance(item,bytes):
                        if not item.startswith(b"\xff\xd8"):
                            raise RuntimeError(which+" VIDEO_NOT_JPEG")
                        frames[which]+=1
                        continue
                    event=json.loads(item)
                    if event.get("type")=="error":
                        raise RuntimeError(which+" STREAM_ERROR "+str(event.get("error",""))[:80])
                    if event.get("type")=="input_ack" and event.get("id")==target:
                        return event
            async def issue(which,ws,name,payload,validator):
                marker=f"switch-{len(records)+1}"
                sent=time.perf_counter()
                await ws.send(json.dumps({"type":"input","id":marker,"payload":payload}))
                result=await get_ack(ws,marker,which)
                ack=time.perf_counter()
                verified,observation=await validator()
                checked=time.perf_counter()
                records.append({
                    "target":which,"action":name,"ack":result.get("ok",False),
                    "device_ms":result.get("device_ms"),
                    "round_trip_ms":round((ack-sent)*1000,1),
                    "total_through_verification_ms":round((checked-sent)*1000,1),
                    "verified":bool(verified),"observed":observation,
                    "error":result.get("error")})
            async def read_pc(expect):
                await asyncio.sleep(0.015)
                xy=cursor()
                return (abs(xy[0]-expect[0])<=3 and abs(xy[1]-expect[1])<=3,
                        "cursor_expected" if abs(xy[0]-expect[0])<=3 and abs(xy[1]-expect[1])<=3 else "cursor_not_at_target")
            async def read_phone(phase):
                obj=(await client.get("/api/v1/phone/ui")).json()
                fg=obj.get("foreground_package","")
                if phase=="home":return ("launcher" in fg,fg)
                if phase=="recents":
                    root=obj.get("root",{})
                    v=json.dumps(root,ensure_ascii=False).lower()
                    return ("systemui" in fg or "recents" in v or "recent apps" in v,fg)
                return (bool(fg),fg)
            # Both native video WebSocket connections stay open through all actions.
            try:
                await issue("pc",pc,"mouse_move_small",
                    {"action":"move","monitor":selected["index"],"x":newx,"y":newy},
                    lambda:read_pc((selected["left"]+newx,selected["top"]+newy)))
                await issue("phone",phone,"home",
                    {"action":"home"},lambda:read_phone("home"))
                await issue("pc",pc,"mouse_restore",
                    {"action":"move","monitor":selected["index"],"x":x,"y":y},
                    lambda:read_pc((selected["left"]+x,selected["top"]+y)))
                await issue("phone",phone,"recents",
                    {"action":"recents"},lambda:read_phone("recents"))
                await issue("pc",pc,"mouse_move_again",
                    {"action":"move","monitor":selected["index"],"x":newx,"y":newy},
                    lambda:read_pc((selected["left"]+newx,selected["top"]+newy)))
                await issue("phone",phone,"back",
                    {"action":"back"},lambda:read_phone("back"))
            finally:
                # Restore original mouse position even when a phone action fails.
                x0=original[0]-selected["left"]
                y0=original[1]-selected["top"]
                if 0<=x0<selected["width"] and 0<=y0<selected["height"]:
                    try:
                        marker="restore-final"
                        await pc.send(json.dumps({"type":"input","id":marker,
                            "payload":{"action":"move","monitor":selected["index"],
                            "x":x0,"y":y0}}))
                        await get_ack(pc,marker,"pc")
                    except Exception:
                        pass
            elapsed=round((time.perf_counter()-start)*1000,1)
        print(json.dumps({
            "test":"persistent-authenticated-worker-pc-phone-switch",
            "pc_and_phone_ws_both_open_entire_test":True,
            "same_worker_endpoint":url.netloc,
            "original_phone_app":before,
            "frame_counts":frames,
            "actions":records,
            "verified_actions":sum(bool(x["verified"]) and bool(x["ack"]) for x in records),
            "action_count":len(records),
            "median_roundtrip_ms":pct([x["round_trip_ms"] for x in records]),
            "median_to_verified_ms":pct([x["total_through_verification_ms"] for x in records]),
            "all_actions_under_10_seconds":all(x["total_through_verification_ms"]<10000 for x in records),
            "session_elapsed_ms":elapsed,
            "pc_cursor_restored":cursor()==original
        },ensure_ascii=False,separators=(",",":")))
if __name__=="__main__":
    asyncio.run(main())
