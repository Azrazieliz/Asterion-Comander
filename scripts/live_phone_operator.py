"""Interactive, state-aware phone operator over Control's persistent WebSocket.

Each command is chosen AFTER inspecting the current Android accessibility tree.
This is a genuine command/response session, not a prewritten workflow.
The optional live video feed is forwarded to an external viewer by the protocol;
this CLI uses the semantic tree and never saves frames or screenshots.
"""
from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
import os
import shlex
import time
from pathlib import Path
from urllib.parse import urlsplit
from websockets.asyncio.client import connect

STATE=Path(os.environ.get("LOCALAPPDATA",str(Path.home())))/"AsterionControl"
DEFAULT_URL="ws://192.168.1.133:8911/api/v1/stream/phone"


def verified_stream_url(value: str) -> str:
    url=urlsplit(value)
    try:
        address=ipaddress.ip_address(url.hostname or "")
        port=url.port
    except ValueError as exc:
        raise ValueError("A private Control IP and explicit port are required") from exc
    if url.scheme!="ws" or url.path!="/api/v1/stream/phone" or not port or (
        not address.is_private and not address.is_loopback
        and address not in ipaddress.ip_network("100.64.0.0/10")
    ):
        raise ValueError("Use the authenticated private Control WebSocket only")
    if url.username or url.password or url.query or url.fragment:
        raise ValueError("Credentials and query parameters are forbidden in the URL")
    return value


def describe(state: dict, limit: int=42) -> dict:
    """Bounded semantic labels; no frame/screenshot images or stored transcripts."""
    nodes=[]
    def walk(node):
        if not isinstance(node,dict) or len(nodes)>=limit:
            return
        label=str(node.get("text") or node.get("description") or "").strip()
        if label:
            nodes.append({"label":label[:160],
                          "bounds":node.get("bounds"),
                          "clickable":bool(node.get("clickable"))})
        for child in node.get("children",[]):
            walk(child)
    walk(state.get("root"))
    return {"foreground_package":state.get("foreground_package"),
            "keyboard":state.get("keyboard"),"labels":nodes}


class LivePhoneOperator:
    def __init__(self,url: str|None=None, video: bool=False):
        self.url=verified_stream_url(url or os.environ.get(
            "ASTERION_CONTROL_LIVE_URL",DEFAULT_URL))
        self.video=video
        self.connection=None
        self.seq=0
        self.state_id=None
        self.state=None
        self.frames_seen=0

    async def __aenter__(self):
        key=(STATE/"control-token.txt").read_text(encoding="utf-8").strip()
        if len(key)<32:
            raise RuntimeError("Owner Control pairing credential unavailable")
        host=urlsplit(self.url)
        origin="http://"+host.netloc
        self.connection=await connect(self.url,origin=origin,
                                      open_timeout=6,close_timeout=2,
                                      max_size=4_200_000)
        await self.connection.send(json.dumps({
            "token":key,"video":self.video,"fps":12}))
        return self

    async def __aexit__(self,*_):
        if self.connection:
            await self.connection.close()
            self.connection=None
        self.state=None;self.state_id=None

    async def _exchange(self,kind: str,payload: dict,reply_type: str):
        if self.connection is None:
            raise RuntimeError("Start the authenticated live Control session first")
        self.seq+=1
        ident="interactive-"+str(self.seq)
        started=time.perf_counter()
        await self.connection.send(json.dumps({"type":kind,"id":ident,**payload},
                                              separators=(",",":")))
        while time.perf_counter()-started<6:
            msg=await asyncio.wait_for(self.connection.recv(),timeout=5)
            if isinstance(msg,bytes):
                self.frames_seen+=1
                continue
            item=json.loads(msg)
            if item.get("type")=="error":
                raise RuntimeError(str(item.get("error","Live connection error"))[:160])
            if item.get("type")==reply_type and item.get("id")==ident:
                item["elapsed_ms"]=round((time.perf_counter()-started)*1000,1)
                return item
        raise TimeoutError("Control response missing; action outcome uncertain")

    async def inspect(self):
        response=await self._exchange("inspect",{},"ui_state")
        if not response.get("ok"):
            self.state_id=None;self.state=None
            raise RuntimeError(response.get("error","UI inspection failed"))
        self.state_id=response["state_id"]
        self.state=response["state"]
        return describe(self.state)

    async def observe_transition(self,previous: dict, timeout_s: float=1.4):
        """Do not confuse a gesture acknowledgment with a loaded page.

        Poll actual Android Accessibility state until it changes; then read
        it once more after settling. If nothing changes, report unverified
        instead of assuming a tap navigated successfully.
        """
        def signature(item):
            return json.dumps({
                "foreground_package":item.get("foreground_package"),
                "keyboard":item.get("keyboard"),
                "root":item.get("root")
            },sort_keys=True,ensure_ascii=False)
        before=signature(previous)
        deadline=time.monotonic()+timeout_s
        seen=None
        while time.monotonic()<deadline:
            await asyncio.sleep(0.085)
            seen=await self.inspect()
            if self.state is not None and signature(self.state)!=before:
                await asyncio.sleep(0.11)
                seen=await self.inspect()
                return {"transition_observed":True,"current":seen}
        return {"transition_observed":False,"current":seen,
                "note":"No changed UI confirmed; inspect before deciding next action"}

    async def action(self,payload: dict):
        if not self.state_id or self.state is None:
            raise RuntimeError("Inspect the current UI before each action")
        if payload.get("action")=="type":
            keyboard=self.state.get("keyboard") or {}
            if keyboard.get("editor_package")=="com.openai.chatgpt" and (
                keyboard.get("draft_empty") is not True):
                raise RuntimeError("ChatGPT draft not confirmed empty; no typing")
        state_id=self.state_id
        package=self.state.get("foreground_package")
        self.state_id=None;self.state=None  # no blind repeated commands
        return await self._exchange("input",{
            "state_id":state_id,"expect_package":package,
            "payload":payload},"input_ack")

    async def launch(self,package: str):
        if not self.state_id or self.state is None:
            raise RuntimeError("Inspect Control before launching another app")
        if self.state.get("foreground_package")!="com.asterion.control":
            raise RuntimeError("Open the foreground Asterion Control app first")
        state_id=self.state_id
        self.state_id=None;self.state=None
        return await self._exchange("launch_app",{
            "state_id":state_id,"expect_package":"com.asterion.control",
            "package":package},"launch_ack")


def command(line: str):
    parts=shlex.split(line)
    if not parts:
        return None,None
    name=parts[0].lower()
    if name in ("quit","exit","help","inspect"):
        return name,None
    if name in ("back","home","recents","notifications") and len(parts)==1:
        return "input",{"action":name}
    if name=="tap" and len(parts)==3:
        return "input",{"action":"tap","x":int(parts[1]),"y":int(parts[2])}
    if name=="click" and len(parts)>=2:
        return "input",{"action":"click_text","text":" ".join(parts[1:])}
    if name=="swipe" and len(parts)==5:
        return "input",{"action":"swipe","x":int(parts[1]),"y":int(parts[2]),
                        "x2":int(parts[3]),"y2":int(parts[4]),
                        "duration_ms":250}
    if name=="type" and len(parts)>=2:
        return "input",{"action":"type","text":" ".join(parts[1:])}
    if name=="launch" and len(parts)==2:
        return "launch",parts[1]
    raise ValueError("Unknown command. Use inspect/tap/click/swipe/back/home/"
                     "recents/notifications/launch/type/quit")


async def main():
    parser=argparse.ArgumentParser(description="State-guarded native phone operator")
    parser.add_argument("--url",help="Owner-paired private Control WebSocket URL")
    parser.add_argument("--video",action="store_true",
                        help="Keep optional authorized continuous native video open")
    args=parser.parse_args()
    async with LivePhoneOperator(args.url,args.video) as operator:
        print("Authenticated live Control. Commands: inspect, tap x y, "
              "click TEXT, swipe x y x2 y2, back, home, recents, "
              "notifications, launch PACKAGE, type TEXT, quit",flush=True)
        print(json.dumps(await operator.inspect(),ensure_ascii=False),flush=True)
        while True:
            try:
                line=await asyncio.to_thread(input,"control> ")
                name,payload=command(line)
                if name is None:continue
                if name in ("quit","exit"):break
                if name=="help":
                    print("One action at a time; every action is bound to the "
                          "last observed UI state.",flush=True)
                    continue
                if name=="inspect":
                    print(json.dumps(await operator.inspect(),
                                     ensure_ascii=False),flush=True)
                    continue
                observed_before=operator.state
                if name=="launch":
                    result=await operator.launch(payload)
                else:
                    result=await operator.action(payload)
                print(json.dumps(result,separators=(",",":")),flush=True)
                if result.get("ok"):
                    outcome=await operator.observe_transition(observed_before)
                    print(json.dumps(outcome,ensure_ascii=False),flush=True)
                else:
                    print("Action not confirmed. Inspect before any retry.",
                          flush=True)
            except (ValueError,RuntimeError,TimeoutError) as exc:
                print("CONTROL_ERROR: "+str(exc)[:180],flush=True)
                operator.state_id=None
                operator.state=None

if __name__=="__main__":
    asyncio.run(main())
