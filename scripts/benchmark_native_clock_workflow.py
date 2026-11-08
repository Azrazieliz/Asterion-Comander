"""Continuous real-app read-only test: launch Samsung Clock, switch tabs, restore ChatGPT.

Direct authenticated Windows-Control <-> Android WebSocket for every tap/swipe,
with same-LAN native /ui semantic checks. GitHub carries only the initial job.
No screenshot calls, audio capture, alarm modification or ChatGPT draft edits.
"""
import asyncio
import json
import os
import statistics
import time
from pathlib import Path
import httpx
from websockets.asyncio.client import connect

state=Path(os.environ.get("LOCALAPPDATA",str(Path.home())))/"AsterionControl"
pair=json.loads((state/"phone-pairing.json").read_text("utf-8"))
phone=pair["base_url"].rstrip("/")
bearer=pair["token"]
win_token=(state/"control-token.txt").read_text("utf-8").strip()
ws_url="ws://192.168.1.133:8911/api/v1/stream/phone"
app="com.sec.android.app.clockpackage"
original="com.openai.chatgpt"

def nodes(x):
    if isinstance(x,dict):
        yield x
        for item in x.get("children",[]):
            yield from nodes(item)

def find(u,terms, bottom=False):
    matches=[]
    for n in nodes(u.get("root",{})):
        vals=[str(n.get("text") or "").strip().lower(),
              str(n.get("description") or "").strip().lower()]
        b=n.get("bounds")
        if not (isinstance(b,list) and len(b)==4 and b[2]>b[0] and b[3]>b[1]):
            continue
        if any(t.lower()==v or (len(t)>4 and t.lower() in v)
               for t in terms for v in vals):
            matches.append(b)
    if not matches:return None
    return max(matches,key=lambda b:b[1]) if bottom else matches[0]

async def main():
    t0=time.perf_counter()
    actions=[];frames=0;opened=False;switched=[];restored=False;blocker=""
    async with httpx.AsyncClient(trust_env=False,follow_redirects=False,timeout=5) as http:
        async def ui():
            t=time.perf_counter()
            r=await http.get(phone+"/ui",headers={"Authorization":"Bearer "+bearer})
            r.raise_for_status()
            return r.json(),round((time.perf_counter()-t)*1000,1)

        first,_=await ui()
        if first.get("foreground_package")!=original:
            print("DIRECT_CLOCK_WORKFLOW "+json.dumps({"status":"not_started",
                  "reason":"Original ChatGPT not foreground",
                  "foreground":first.get("foreground_package")}))
            return
        draft_present=bool((first.get("keyboard") or {}).get("active")
                     and (first.get("keyboard") or {}).get("draft_empty") is not True)
        async with connect(ws_url,origin="http://192.168.1.133:8911",
                           open_timeout=6,close_timeout=2,max_size=4_200_000) as ws:
            await ws.send(json.dumps({"token":win_token,"monitor":1,"fps":10}))
            async def act(name,payload):
                nonlocal frames
                key="clock-"+str(len(actions))+"-"+str(time.monotonic_ns())
                ts=time.perf_counter()
                await ws.send(json.dumps({"type":"input","id":key,"payload":payload}))
                while time.perf_counter()-ts<5:
                    message=await asyncio.wait_for(ws.recv(),timeout=4)
                    if isinstance(message,bytes):
                        frames+=1;continue
                    event=json.loads(message)
                    if event.get("type")=="error":raise RuntimeError("Live stream failure")
                    if event.get("type")=="input_ack" and event.get("id")==key:
                        result={"step":name,"ok":bool(event.get("ok")),
                                "rtt_ms":round((time.perf_counter()-ts)*1000,1),
                                "device_ms":event.get("device_ms")}
                        actions.append(result)
                        if not result["ok"]:raise RuntimeError("Input rejected: "+name)
                        await asyncio.sleep(.095)
                        return
                raise TimeoutError(name)

            async def tap(name,b):
                await act(name,{"action":"tap","x":(b[0]+b[2])//2,
                                "y":(b[1]+b[3])//2})

            async def until(package,timeout=2.3):
                start=time.perf_counter()
                while time.perf_counter()-start<timeout:
                    u,_=await ui()
                    if u.get("foreground_package")==package:return u
                    await asyncio.sleep(.12)
                return None

            try:
                # Open the already-running Asterion Control task in native
                # Recents. Unlike the launcher search, this requires no typing.
                await act("open_recents_for_Control",{"action":"recents"})
                control_open=False
                for attempt in range(4):
                    u,_=await ui()
                    b_control=find(u,["Asterion Control"])
                    if b_control:
                        # Use the exposed edge of stacked Samsung task cards.
                        x=min(b_control[2]-10,b_control[0]+22)
                        y=(b_control[1]+b_control[3])//2
                        await act("select_Control_recent_"+str(attempt+1),
                                  {"action":"tap","x":x,"y":y})
                        if await until("com.asterion.control",1.0) is not None:
                            control_open=True;break
                    await act("scroll_recents_to_Control_"+str(attempt+1),
                              {"action":"swipe","x":275,"y":1070,
                               "x2":830,"y2":1070,"duration_ms":220})
                if not control_open:
                    raise RuntimeError("Asterion Control native task could not be opened")

                # This approved phone-native API launches only an installed app
                # while Control is visibly foreground; it is not an ADB shell.
                ts=time.perf_counter()
                response=await http.post(phone+"/apps/launch",
                    headers={"Authorization":"Bearer "+bearer},
                    json={"package":app},timeout=4)
                response.raise_for_status()
                launch=response.json()
                dispatched=launch.get("intent_dispatched") is True
                actions.append({"step":"launch_Clock_native_app_catalog",
                                "ok":dispatched,
                                "rtt_ms":round((time.perf_counter()-ts)*1000,1),
                                "device_ms":None})
                if not dispatched:
                    raise RuntimeError("Owner-approved native launch was denied: "
                                       +str(launch.get("reason","unknown"))[:90])
                if await until(app,timeout=3.2) is None:
                    raise RuntimeError("Clock did not become foreground after native launch")
                opened=True
                for title in ("World clock","Stopwatch","Timer","Alarm"):
                    u,_=await ui()
                    b=find(u,[title],bottom=True)
                    if not b:continue
                    await tap("select_"+title.replace(" ","_"),b)
                    u,_=await ui()
                    if u.get("foreground_package")!=app:
                        raise RuntimeError("Clock closed while selecting tab")
                    switched.append(title)
                if len(switched)<2:
                    raise RuntimeError("Fewer than two Clock tabs are accessible")
            except Exception as exc:
                blocker=str(exc)[:165]
            finally:
                # Use native Recents so the original conversation draft remains intact.
                try:
                    u,_=await ui()
                    if u.get("foreground_package")==original:
                        restored=True
                    else:
                        await act("open_recents",{"action":"recents"})
                        for j in range(5):
                            u,_=await ui()
                            if u.get("foreground_package")==original:
                                restored=True;break
                            b=find(u,["ChatGPT"])
                            if b:
                                await act("return_to_ChatGPT_"+str(j+1),{
                                    "action":"tap","x":min(b[2]-15,b[0]+55),
                                    "y":(b[1]+b[3])//2})
                                if await until(original,.7) is not None:
                                    restored=True;break
                            await act("move_recents_card_"+str(j+1),{
                                "action":"swipe","x":830,"y":1000,
                                "x2":255,"y2":1000,"duration_ms":220})
                except Exception:
                    pass
            # Allow animations to complete before reporting restoration.
            if not restored:
                u,_=await ui()
                restored=u.get("foreground_package")==original
            times=[a["rtt_ms"] for a in actions if a["ok"]]
            out={"status":"completed" if opened and len(switched)>=2 and restored else "partial",
                 "app":"Samsung Clock","app_opened":opened,
                 "tabs_navigated":switched,
                 "original_chatgpt_restored":restored,
                 "original_draft_not_edited":True,
                 "draft_preexisting":draft_present,
                 "native_actions":len(actions),
                 "median_action_ack_ms":round(statistics.median(times),1) if times else None,
                 "fastest_ack_ms":min(times) if times else None,
                 "slowest_ack_ms":max(times) if times else None,
                 "total_workflow_ms":round((time.perf_counter()-t0)*1000,1),
                 "live_frames_received":frames,
                 "first_actions":actions[:6],"last_actions":actions[-5:],
                 "blocker":blocker}
            print("DIRECT_CLOCK_WORKFLOW "+json.dumps(out,separators=(",",":")),flush=True)

if __name__=="__main__":
    asyncio.run(main())
