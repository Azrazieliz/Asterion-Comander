"""Phone-initiated authenticated WebSocket backchannel for direct Android native RPC.

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

from .diagnostic_core import try_record
from .pairing import is_authorized as paired_device_is_authorized
from .phone_bridge import load as load_registered_phone
from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

# Use the canonical Windows Control pairing ledger. It is written by
# POST /api/v1/pair and is shared by both native agent and native RPC gateway.
# Do not keep a second inconsistent copy under LOCALAPPDATA.
router = APIRouter()
_active: WebSocket | None = None
_active_registration: str | None = None
_pending: dict[str, asyncio.Future] = {}
_send_lock = asyncio.Lock()


class DirectPhoneUncertain(RuntimeError):
    pass


def _authorized(candidate: str) -> bool:
    # The Android primary device uses the SAME native agent token already
    # registered through /api/v1/phone/register. Its revocation immediately
    # removes cellular access, and there is no extra PC pairing requirement.
    if not isinstance(candidate, str) or not (32 <= len(candidate) <= 512):
        return False
    record = load_registered_phone()
    registered = record.get("token") if isinstance(record, dict) else None
    if isinstance(registered, str) and len(registered) >= 32:
        if hmac.compare_digest(candidate.encode(), registered.encode()):
            return True
    # Preserve compatibility with an existing owner-approved Windows pairing.
    return paired_device_is_authorized(candidate)


def _registration_identity() -> str | None:
    record=load_registered_phone()
    token=record.get("token") if isinstance(record,dict) else None
    return hashlib.sha256(token.encode()).hexdigest() if isinstance(token,str) and token else None


def _session_authorized(ws: WebSocket) -> bool:
    header=ws.headers.get("authorization","")
    return (header.startswith("Bearer ") and
            _active_registration==_registration_identity() and _authorized(header[7:]))


def connected() -> bool:
    return _active is not None and _session_authorized(_active)


def _fail_pending(reason: str) -> None:
    for future in list(_pending.values()):
        if not future.done():
            future.set_exception(DirectPhoneUncertain(reason))
    _pending.clear()


@router.websocket("/phone/live")
async def phone_live(ws: WebSocket):
    global _active, _active_registration
    header = ws.headers.get("authorization", "")
    # Record exact server-side rejection stage, NEVER the bearer or source IP.
    if not header.startswith("Bearer ") or not _authorized(header[7:]):
        try_record("security_failure",component="phone_wss_relay",severity="warning",
                   state="failed",attributes={"stage":"authorization",
                       "reason":"missing_bearer_header" if not header.startswith("Bearer ") else "unapproved_phone_key"})
        await ws.close(code=1008)
        return
    async with _send_lock:
        # A newly registered key must never be routed to an obsolete socket.
        # Only retire a provably revoked session; a live authorized socket
        # keeps its original no-replacement/no-replay behavior.
        if _active is not None:
            if _session_authorized(_active):
                try_record("transport_error",component="phone_wss_relay",severity="warning",
                           state="failed",attributes={"stage":"upgrade","reason":"session_already_active"})
                await ws.close(code=1008)
                return
            revoked=_active
            _active=None
            _active_registration=None
            _fail_pending("Phone pairing changed; previous request outcome uncertain")
            try:
                await revoked.close(code=1008)
            except (RuntimeError,WebSocketDisconnect,OSError):
                pass
        # Recheck after the previous asynchronous close.
        if not _authorized(header[7:]):
            await ws.close(code=1008)
            return
        registration=_registration_identity()
        await ws.accept()
        _active=ws
        _active_registration=registration
    try_record("phone_connected",component="phone_wss_relay",state="connected",
               attributes={"stage":"websocket_accepted"})
    try:
        while True:
            raw = await ws.receive_text()
            if _active is not ws:
                break
            if not _session_authorized(ws):
                await ws.close(code=1008)
                break
            if len(raw) > 8_000_000:
                raise ValueError("Android native RPC result too large")
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
                future.set_exception(DirectPhoneUncertain("Invalid phone native RPC response"))
            else:
                future.set_result(response)
    except (WebSocketDisconnect, ValueError, RuntimeError):
        pass
    finally:
        if _active is ws:
            _active = None
            _active_registration = None
            try_record("transport_error",component="phone_wss_relay",severity="warning",
                       state="disconnected",attributes={"stage":"session_end"})
            _fail_pending("Phone direct HTTPS session dropped; outcome uncertain")


async def invoke(rpc: dict[str, Any], timeout: float = 22.0) -> dict:
    ws = _active
    if ws is None or not _session_authorized(ws):
        raise ConnectionError("Phone direct cellular connection is offline")
    method = rpc.get("method")
    if method not in ("tools/call", "tools/list", "ping"):
        raise ValueError("Unsupported Android native RPC relay method")
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
            if _active is not ws or not _session_authorized(ws):
                raise DirectPhoneUncertain("Phone session or pairing changed before dispatch")
            await ws.send_text(json.dumps({"id": id_, "rpc": rpc}, separators=(",", ":")))
        # Timeout means the phone might have executed the request.
        return await asyncio.wait_for(future, timeout)
    except (asyncio.TimeoutError, WebSocketDisconnect, RuntimeError, OSError) as exc:
        raise DirectPhoneUncertain("Android direct native RPC command outcome uncertain") from exc
    finally:
        _pending.pop(id_, None)
        if not future.done():
            future.cancel()
