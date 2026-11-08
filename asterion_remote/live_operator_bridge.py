"""Resident state-aware Android operator for the authenticated Control MCP gateway.

The gateway's existing OAuth and private Windows Control token authorize the
session. One persistent WebSocket connects to the already owner-paired native
Windows/phone control server; every ChatGPT tool call executes one action, not a
prewritten sequence. Neither UI content nor credentials are logged or saved.
"""
from __future__ import annotations

import asyncio
import json
import secrets
import time
from urllib.parse import urlsplit

from websockets.asyncio.client import connect


class LiveOperatorUnavailable(RuntimeError):
    pass


class LiveOperator:
    def __init__(self):
        self._socket=None
        self._lock=asyncio.Lock()
        self._route=None
        self._last_state=None
        self._counter=0

    async def _close(self):
        ws,self._socket=self._socket,None
        self._last_state=None
        if ws is not None:
            try:
                await ws.close()
            except Exception:
                pass

    async def _attach(self,route:tuple[str,str]):
        base,token=route
        parsed=urlsplit(base)
        if parsed.scheme!="http" or parsed.port!=8911 or parsed.path!="/mcp":
            raise LiveOperatorUnavailable("Canonical private Windows Control MCP route missing")
        websocket_url="ws://"+parsed.netloc+"/api/v1/stream/phone"
        if self._socket is not None and self._route==(websocket_url,token):
            return
        await self._close()
        try:
            self._socket=await connect(websocket_url,
                origin="http://"+parsed.netloc,open_timeout=4,close_timeout=2,
                max_size=2_000_000,ping_interval=15,ping_timeout=8)
            await self._socket.send(json.dumps({"token":token,"video":False,"fps":1}))
            self._route=(websocket_url,token)
        except Exception as exc:
            await self._close()
            raise LiveOperatorUnavailable("Private real-time Control connection unavailable") from exc

    async def _command(self,kind,payload,expected,timeout=6):
        self._counter+=1
        ident="operator-"+secrets.token_hex(12)
        sent=time.perf_counter()
        try:
            await self._socket.send(json.dumps(
                {"type":kind,"id":ident,**payload},separators=(",",":")))
            while time.perf_counter()-sent<timeout:
                event=await asyncio.wait_for(self._socket.recv(),timeout=timeout)
                if isinstance(event,bytes):
                    continue
                response=json.loads(event)
                if response.get("type")=="error":
                    raise LiveOperatorUnavailable("Live Control protocol returned an error")
                if response.get("type")==expected and response.get("id")==ident:
                    response["roundtrip_ms"]=round((time.perf_counter()-sent)*1000,1)
                    return response
            raise asyncio.TimeoutError("No Control response")
        except (asyncio.TimeoutError,ConnectionError,RuntimeError,OSError) as exc:
            await self._close()
            # Never retry an input automatically: it might have executed.
            raise LiveOperatorUnavailable(
                "Control result uncertain; inspect phone state before another action") from exc

    async def inspect(self,route):
        async with self._lock:
            await self._attach(route)
            result=await self._command("inspect",{},"ui_state")
            if not result.get("ok") or not isinstance(result.get("state"),dict):
                self._last_state=None
                return result
            state=result["state"]
            self._last_state={
                "id":result.get("state_id"),
                "foreground_package":state.get("foreground_package"),
                "keyboard":state.get("keyboard") or {},
            }
            return result

    async def action(self,route,args:dict):
        async with self._lock:
            state=self._last_state
            state_id=args.get("state_id")
            if state is None or not isinstance(state_id,str) or state_id!=state.get("id"):
                return {"ok":False,"error":"Inspect current UI first; state token absent or mismatched"}
            action=args.get("action")
            if action not in ("tap","swipe","long_press","back","home","recents",
                              "notifications","type","click_text"):
                return {"ok":False,"error":"Unsupported native Android action"}
            if action=="type" and state["foreground_package"]=="com.openai.chatgpt":
                keyboard=state["keyboard"]
                if keyboard.get("editor_package")!="com.openai.chatgpt" or keyboard.get("draft_empty") is not True:
                    return {"ok":False,"error":"ChatGPT draft or keyboard not safely editable"}
            payload={"action":action}
            for field in ("x","y","x2","y2","duration_ms","text"):
                if field in args: payload[field]=args[field]
            if action in ("tap","long_press") and ("x" not in payload or "y" not in payload):
                return {"ok":False,"error":"Tap coordinates required"}
            if action=="click_text" and not payload.get("text"):
                return {"ok":False,"error":"Text label required"}
            if action=="type" and not payload.get("text"):
                return {"ok":False,"error":"Nonempty text required"}
            await self._attach(route)
            # Consume the observation before attempting dispatch.
            self._last_state=None
            return await self._command("input",{
                "state_id":state_id,
                "expect_package":state["foreground_package"],
                "payload":payload,
            },"input_ack")

    async def launch(self,route,args:dict):
        async with self._lock:
            state=self._last_state
            if not state or args.get("state_id")!=state.get("id"):
                return {"ok":False,"error":"Inspect current UI first"}
            if state.get("foreground_package")!="com.asterion.control":
                return {"ok":False,"error":"Asterion Control must be foreground to launch apps"}
            package=args.get("package")
            if not isinstance(package,str) or not 3<=len(package)<=180:
                return {"ok":False,"error":"Installed Android application package required"}
            await self._attach(route)
            self._last_state=None
            return await self._command("launch_app",{
                "state_id":state["id"],"expect_package":"com.asterion.control",
                "package":package,
            },"launch_ack")


OPERATOR=LiveOperator()
