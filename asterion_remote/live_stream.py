"""Authenticated full-duplex LAN video + input WebSocket for Asterion Control.

Android is the controller, Windows is a worker. This transport does not use GitHub,
ADB, Work, or Desktop Commander. Private LAN only unless an encrypted authenticated
VPN is provisioned. The WebSocket handshake requires a previously paired token.
"""
from __future__ import annotations

import asyncio
import contextlib
import secrets
import time
import httpx
from fastapi import WebSocket, WebSocketDisconnect

from .security import configured_token
from .pairing import is_authorized
from .phone_bridge import load as load_phone_pairing


def install_stream(app, desktop_capture, desktop_input):
    @app.websocket('/api/v1/stream/{source}')
    async def stream(websocket: WebSocket, source: str):
        if source not in ('desktop', 'phone'):
            await websocket.close(code=1008)
            return

        origin=websocket.headers.get('origin','')
        allowed_origin=f"{'https' if websocket.url.scheme == 'wss' else 'http'}://{websocket.headers.get('host','')}"
        if origin and origin != allowed_origin:
            await websocket.close(code=1008)
            return

        await websocket.accept()
        try:
            initial=await asyncio.wait_for(websocket.receive_json(),timeout=5)
            key=initial.get('token') if isinstance(initial,dict) else ''
            if not isinstance(key,str) or not (secrets.compare_digest(key,configured_token()) or is_authorized(key)):
                await websocket.close(code=1008)
                return
            monitor=max(0,min(16,int(initial.get('monitor',1))))
            fps=max(1,min(20,int(initial.get('fps',12))))
        except (ValueError,TypeError,asyncio.TimeoutError,WebSocketDisconnect):
            with contextlib.suppress(Exception): await websocket.close(code=1008)
            return

        phone=load_phone_pairing() if source=='phone' else None
        if source=='phone' and phone is None:
            await websocket.send_json({'type':'error','error':'Phone agent is not paired'})
            await websocket.close(code=1011)
            return

        connection=httpx.Client(timeout=3.5,trust_env=False,follow_redirects=False) if phone else None
        headers={'Authorization':'Bearer '+phone['token']} if phone else None
        outgoing=asyncio.Lock()
        closed=asyncio.Event()
        last_action=0.0

        async def report(payload):
            async with outgoing:
                await websocket.send_json(payload)

        async def push_frames():
            interval=1/fps
            while not closed.is_set():
                start=time.perf_counter()
                if source=='desktop':
                    frame=await asyncio.to_thread(desktop_capture,monitor)
                else:
                    response=await asyncio.to_thread(
                        connection.get,phone['base_url']+'/screen',headers=headers)
                    response.raise_for_status()
                    frame=response.content
                if not frame or len(frame)>4_000_000:
                    raise ValueError('Invalid frame payload')
                async with outgoing:
                    await websocket.send_bytes(frame)
                await asyncio.sleep(max(.005,interval-(time.perf_counter()-start)))

        async def pull_actions():
            nonlocal last_action
            while not closed.is_set():
                request=await websocket.receive_json()
                if not isinstance(request,dict) or request.get('type')!='input':
                    await report({'type':'error','error':'Expected input message'})
                    continue
                ident=request.get('id')
                if not isinstance(ident,str) or not 1<=len(ident)<=64:
                    await report({'type':'error','error':'Invalid input request ID'})
                    continue
                started=time.perf_counter()
                now=time.monotonic()
                if now-last_action<0.025:
                    await report({'type':'input_ack','id':ident,'ok':False,'error':'Input rate limited'})
                    continue
                last_action=now
                try:
                    payload=request.get('payload')
                    if not isinstance(payload,dict):
                        raise ValueError('Input payload must be an object')
                    if source=='desktop':
                        result=await asyncio.to_thread(desktop_input,payload)
                    else:
                        from .phone_bridge import PhoneInput
                        action=PhoneInput(**payload)
                        response=await asyncio.to_thread(
                            connection.post,phone['base_url']+'/input',
                            json=action.model_dump(exclude_none=True),headers=headers)
                        response.raise_for_status()
                        result=response.json()
                    if not isinstance(result,dict) or result.get('ok') is not True:
                        raise ValueError('Device did not confirm the requested input')
                    await report({'type':'input_ack','id':ident,'ok':True,
                                  'device_ms':round((time.perf_counter()-started)*1000,1)})
                except Exception as exc:
                    await report({'type':'input_ack','id':ident,'ok':False,
                                  'error':type(exc).__name__+': '+str(exc)[:160]})

        first=None
        second=None
        try:
            first=asyncio.create_task(push_frames())
            second=asyncio.create_task(pull_actions())
            done,pending=await asyncio.wait({first,second},return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                try: await task
                except (WebSocketDisconnect,asyncio.CancelledError): pass
                except Exception as exc:
                    with contextlib.suppress(Exception):
                        await report({'type':'error','error':type(exc).__name__+': '+str(exc)[:140]})
        finally:
            closed.set()
            for task in (first,second):
                if task and not task.done():task.cancel()
            for task in (first,second):
                if task:
                    with contextlib.suppress(Exception,asyncio.CancelledError):await task
            if connection:connection.close()
            with contextlib.suppress(Exception):await websocket.close()
