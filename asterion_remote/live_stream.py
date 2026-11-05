"""Continuous authenticated websocket screen-stream bridge.
No embedded AI; frames are sampled from native capture or authorized Android agent.
"""
from __future__ import annotations
import asyncio
import secrets
import time
from fastapi import WebSocket, WebSocketDisconnect
from .security import configured_token
from .phone_bridge import request as phone_request


def install_stream(app, desktop_capture):
    @app.websocket('/api/v1/stream/{source}')
    async def stream(websocket: WebSocket, source: str):
        if source not in ('desktop','phone'):
            await websocket.close(code=1008);return
        origin=websocket.headers.get('origin','')
        allowed_origin=f"{'https' if websocket.url.scheme == 'wss' else 'http'}://{websocket.headers.get('host','')}"
        if origin and origin != allowed_origin:
            await websocket.close(code=1008);return
        await websocket.accept()
        try:
            first=await asyncio.wait_for(websocket.receive_json(),timeout=5)
            token=first.get('token') if isinstance(first,dict) else ''
            if not isinstance(token,str) or not secrets.compare_digest(token,configured_token()):
                await websocket.close(code=1008);return
            monitor=int(first.get('monitor',1));fps=max(1,min(20,int(first.get('fps',12))))
            interval=1/fps
            while True:
                start=time.monotonic()
                if source=='desktop':
                    image=await asyncio.to_thread(desktop_capture,monitor)
                else:
                    response=await asyncio.to_thread(phone_request,'/screen')
                    image=response.content
                await websocket.send_bytes(image)
                await asyncio.sleep(max(.005,interval-(time.monotonic()-start)))
        except (WebSocketDisconnect, asyncio.CancelledError): pass
        except Exception as exc:
            try: await websocket.send_json({'error':type(exc).__name__+': '+str(exc)[:200]})
            except Exception: pass
            try: await websocket.close()
            except Exception: pass
