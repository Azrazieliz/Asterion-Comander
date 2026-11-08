"""Authenticated full-duplex LAN video + input WebSocket for Asterion Control.

Android is the controller, Windows is a worker. This transport does not use GitHub,
ADB, Work, or Desktop Commander. Private LAN only unless an encrypted authenticated
VPN is provisioned. The WebSocket handshake requires a previously paired token.
"""
from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import secrets
import time
from collections import deque
import httpx
from fastapi import WebSocket, WebSocketDisconnect

from .security import configured_token
from .pairing import is_authorized
from .phone_bridge import load as load_phone_pairing


def _take_mjpeg_frame(buffer: bytearray) -> bytes | None:
    """Return a complete fresh JPEG from one native authenticated MJPEG stream."""
    import re
    marker=b'--asterionframe\r\n'
    start=buffer.find(marker)
    if start<0:
        if len(buffer)>len(marker):del buffer[:-len(marker)]
        return None
    if start:del buffer[:start]
    end=buffer.find(b'\r\n\r\n',len(marker))
    if end<0:
        if len(buffer)>4096:raise ValueError('Invalid MJPEG frame headers')
        return None
    match=re.search(rb'(?i)content-length:\s*(\d+)',bytes(buffer[len(marker):end]))
    if not match:raise ValueError('Missing MJPEG frame length')
    length=int(match.group(1))
    if not 4<=length<=4_000_000:raise ValueError('MJPEG frame size exceeded')
    done=end+4+length+2
    if len(buffer)<done:return None
    frame=bytes(buffer[end+4:end+4+length])
    if not frame.startswith(b'\xff\xd8') or not frame.endswith(b'\xff\xd9'):
        raise ValueError('Malformed JPEG frame')
    del buffer[:done]
    return frame


def _ui_fingerprint(state: dict) -> str:
    """Only a short-lived, in-memory hash of the observed Android UI tree.

    Deliberately includes the foreground package, labels, and bounds; a changed
    page invalidates an older action instead of applying a prewritten click.
    UI text and coordinates are never persisted to disk by the transport.
    """
    if not isinstance(state, dict):
        raise ValueError("Android UI returned a non-object state")
    stable = {
        "foreground_package": state.get("foreground_package"),
        "keyboard": state.get("keyboard"),
        "root": state.get("root"),
    }
    encoded = json.dumps(stable, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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
            # A semantic-only session works when the owner has stopped visual
            # sharing; video=true preserves the existing continuous stream.
            video=initial.get('video',True)
            if not isinstance(video,bool):
                raise ValueError('video must be a boolean')
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
        last_observation: dict | None = None
        seen_requests: set[str] = set()
        seen_order: deque[str] = deque()

        async def phone_ui() -> dict:
            if source != 'phone' or phone is None or connection is None:
                raise ValueError('Android UI inspection is phone-only')
            response=await asyncio.to_thread(
                connection.get,phone['base_url']+'/ui',headers=headers)
            response.raise_for_status()
            state=response.json()
            if not isinstance(state,dict) or not state.get('available'):
                raise ValueError('Native Android accessibility UI unavailable')
            return state

        def remember_id(ident: str) -> bool:
            if ident in seen_requests:
                return False
            seen_requests.add(ident)
            seen_order.append(ident)
            if len(seen_order)>512:
                seen_requests.discard(seen_order.popleft())
            return True

        async def report(payload):
            async with outgoing:
                await websocket.send_json(payload)

        async def push_frames():
            interval=1/fps
            if source=='phone':
                # Preserve one owner-authorized LAN connection for the native
                # continuous stream. Avoid a new stale screenshot GET per frame.
                async with httpx.AsyncClient(timeout=httpx.Timeout(6.0,read=6.0),
                                            trust_env=False,follow_redirects=False) as stream_client:
                    async with stream_client.stream('GET',phone['base_url']+'/stream',headers=headers) as response:
                        response.raise_for_status()
                        buf=bytearray()
                        last_push=0.0
                        async for chunk in response.aiter_bytes():
                            if closed.is_set():break
                            buf.extend(chunk)
                            while True:
                                frame=_take_mjpeg_frame(buf)
                                if frame is None:break
                                now=time.perf_counter()
                                if now-last_push>=interval*0.95:
                                    async with outgoing:await websocket.send_bytes(frame)
                                    last_push=now
                return
            while not closed.is_set():
                start=time.perf_counter()
                frame=await asyncio.to_thread(desktop_capture,monitor)
                if not frame or len(frame)>4_000_000:
                    raise ValueError('Invalid frame payload')
                async with outgoing:await websocket.send_bytes(frame)
                await asyncio.sleep(max(.005,interval-(time.perf_counter()-start)))

        async def pull_actions():
            nonlocal last_action,last_observation
            while not closed.is_set():
                request=await websocket.receive_json()
                if not isinstance(request,dict):
                    await report({'type':'error','error':'Expected JSON object'})
                    continue
                kind=request.get('type')
                if kind not in ('input','inspect','launch_app'):
                    await report({'type':'error','error':'Expected input, inspect, or launch_app'})
                    continue
                ident=request.get('id')
                if not isinstance(ident,str) or not 1<=len(ident)<=64:
                    await report({'type':'error','error':'Invalid action request ID'})
                    continue
                reply_type={'input':'input_ack','inspect':'ui_state',
                            'launch_app':'launch_ack'}[kind]
                if not remember_id(ident):
                    await report({'type':reply_type,'id':ident,'ok':False,
                                  'error':'Duplicate request ID; action not replayed'})
                    continue

                if kind=='inspect':
                    try:
                        state=await phone_ui()
                        last_observation={
                            'id':secrets.token_urlsafe(18),
                            'fingerprint':_ui_fingerprint(state),
                            'when':time.monotonic(),
                        }
                        await report({'type':'ui_state','id':ident,'ok':True,
                                      'state_id':last_observation['id'],
                                      'state':state})
                    except Exception as exc:
                        last_observation=None
                        await report({'type':'ui_state','id':ident,'ok':False,
                                      'error':type(exc).__name__+': '+str(exc)[:120]})
                    continue

                started=time.perf_counter()
                now=time.monotonic()
                if now-last_action<0.025:
                    await report({'type':reply_type,'id':ident,'ok':False,
                                  'error':'Input rate limited'})
                    continue
                last_action=now
                try:
                    if kind=='launch_app' and source!='phone':
                        raise ValueError('App launch is phone-only')
                    if source=='phone':
                        state_id=request.get('state_id')
                        # Compatibility: older clients may omit state_id. The
                        # interactive default uses it for every operation.
                        if state_id is not None:
                            observed=last_observation
                            last_observation=None   # one observation -> one action
                            if not observed or state_id!=observed['id']:
                                raise ValueError('Missing or mismatched UI state; inspect again')
                            if now-observed['when']>10.0:
                                raise ValueError('UI state expired; inspect again')
                            fresh=await phone_ui()
                            if _ui_fingerprint(fresh)!=observed['fingerprint']:
                                raise ValueError('Android UI changed; inspect again')
                        expected=request.get('expect_package')
                        if expected is not None:
                            if not isinstance(expected,str) or not expected:
                                raise ValueError('Invalid expected Android package')
                            if state_id is None:
                                fresh=await phone_ui()
                            if fresh.get('foreground_package')!=expected:
                                raise ValueError('Wrong foreground Android app; no action sent')

                    if kind=='launch_app':
                        package=request.get('package')
                        if not isinstance(package,str) or len(package)>180:
                            raise ValueError('Invalid app package')
                        response=await asyncio.to_thread(
                            connection.post,phone['base_url']+'/apps/launch',
                            json={'package':package},headers=headers)
                        response.raise_for_status()
                        launch=response.json()
                        success=isinstance(launch,dict) and launch.get('intent_dispatched') is True
                        await report({'type':'launch_ack','id':ident,'ok':success,
                                      'intent_dispatched':success,
                                      'verified_foreground':False,
                                      'device_ms':round((time.perf_counter()-started)*1000,1),
                                      **({} if success else
                                         {'error':str(launch.get('reason','Not dispatched'))[:160]})})
                    else:
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
                    await report({'type':reply_type,'id':ident,'ok':False,
                                  'error':type(exc).__name__+': '+str(exc)[:160]})

        first=None
        second=None
        try:
            first=asyncio.create_task(push_frames()) if video else None
            second=asyncio.create_task(pull_actions())
            active_tasks={task for task in (first,second) if task is not None}
            done,pending=await asyncio.wait(active_tasks,return_when=asyncio.FIRST_COMPLETED)
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
