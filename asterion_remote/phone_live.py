"""Phone-initiated authenticated WebSocket backchannel for direct Android MCP.

No GitHub polling, no public Android listener, no cloud model. The phone
uses its existing Windows pairing credential over TLS. Disconnections or
timeouts are uncertain outcomes: a dispatched request is never replayed.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path
from typing import Any

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

STATE = Path(os.environ.get(
    "ASTERION_CONTROL_STATE",
    str(Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "AsterionControl"),
))
AUTHORIZED = STATE / "authorized-devices.json"
router = APIRouter()
_active: WebSocket | None = None
_pending: dict[str, asyncio.Future] = {}
_send_lock = asyncio.Lock()


class DirectPhoneUncertain(RuntimeError):
    pass


def _authorized(candidate: str) -> bool:
    if len(candidate) < 32 or len(candidate) > 512:
        return False
    try:
        records = json.loads(AUTHORIZED.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            return False
        digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
        return any(isinstance(row, dict) and
                   hmac.compare_digest(str(row.get("hash", "")), digest)
                   for row in records)
    except (ValueError, OSError):
        return False


def connected() -> bool:
    return _active is not None


def _fail_pending(reason: str) -> None:
    for future in list(_pending.values()):
        if not future.done():
            future.set_exception(DirectPhoneUncertain(reason))
    _pending.clear()


@router.websocket("/phone/live")
async def phone_live(ws: WebSocket):
    global _active
    header = ws.headers.get("authorization", "")
    if not header.startswith("Bearer ") or not _authorized(header[7:]):
        await ws.close(code=1008)
        return
    if _active is not None:
        # Never replace an in-flight session and silently replay its requests.
        await ws.close(code=1008)
        return
    await ws.accept()
    _active = ws
    try:
        while True:
            raw = await ws.receive_text()
            if len(raw) > 8_000_000:
                raise ValueError("Android MCP result too large")
            message = json.loads(raw)
            if not isinstance(message, dict):
                continue
            if message.get("pong") is True:
                continue
            id_ = message.get("id")
            if not isinstance(id_, str):
                continue
            future = _pending.pop(id_, None)
            if future is None or future.done():
                continue
            response = message.get("rpc")
            if not isinstance(response, dict) or response.get("jsonrpc") != "2.0":
                future.set_exception(DirectPhoneUncertain("Invalid phone MCP response"))
            else:
                future.set_result(response)
    except (WebSocketDisconnect, ValueError, RuntimeError):
        pass
    finally:
        if _active is ws:
            _active = None
            _fail_pending("Phone direct HTTPS session dropped; outcome uncertain")


async def invoke(rpc: dict[str, Any], timeout: float = 22.0) -> dict:
    ws = _active
    if ws is None:
        raise ConnectionError("Phone direct cellular connection is offline")
    method = rpc.get("method")
    if method not in ("tools/call", "tools/list", "ping"):
        raise ValueError("Unsupported Android MCP relay method")
    if method == "tools/call":
        params = rpc.get("params")
        name = params.get("name") if isinstance(params, dict) else None
        if not isinstance(name, str) or not name.startswith("control_phone_"):
            raise ValueError("Not an Android Control tool")
    id_ = secrets.token_hex(16)
    future = asyncio.get_running_loop().create_future()
    _pending[id_] = future
    try:
        async with _send_lock:
            if _active is not ws:
                raise DirectPhoneUncertain("Phone session changed before dispatch")
            await ws.send_text(json.dumps({"id": id_, "rpc": rpc}, separators=(",", ":")))
        # Timeout means the phone might have executed the request.
        return await asyncio.wait_for(future, timeout)
    except (asyncio.TimeoutError, WebSocketDisconnect, RuntimeError, OSError) as exc:
        raise DirectPhoneUncertain("Android direct MCP command outcome uncertain") from exc
    finally:
        _pending.pop(id_, None)
        if not future.done():
            future.cancel()
