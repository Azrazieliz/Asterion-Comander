"""Loopback-only adapter to the EXISTING phone-outbound native WSS session.

The Windows API and the native WSS relay run in separate processes. This small,
authenticated local RPC endpoint lets the Windows worker use the already-paired
Android connection when the saved private-LAN address is unreachable (cellular).
It is NOT an HTTP MCP gateway and must never listen on a public interface.
"""
from __future__ import annotations

import hmac
import base64
import binascii
import json
import re
import secrets
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .native_phone_live import DirectPhoneUncertain, connected, invoke
from .phone_bridge import load as load_registered_phone

router = APIRouter()

# These names are the installed AndroidMcp.java tool names. Do not permit
# arbitrary tools, shell commands, URLs, paths or unapproved partner actions.
ROUTES: dict[tuple[str, str], str] = {
    ("GET", "/health"): "control_phone_health",
    ("POST", "/transfer/start"): "control_phone_transfer_start",
    ("POST", "/transfer/chunk"): "control_phone_transfer_chunk",
    ("POST", "/transfer/status"): "control_phone_transfer_status",
    ("POST", "/transfer/finish"): "control_phone_transfer_finish",
    ("POST", "/transfer/cancel"): "control_phone_transfer_cancel",
    ("GET", "/ui"): "control_phone_ui",
    ("GET", "/screen"): "control_phone_screen",
    ("GET", "/apps"): "control_phone_apps",
    ("POST", "/apps/launch"): "control_phone_app_launch",
    ("GET", "/app-bridge/apps"): "control_phone_app_bridges",
    ("POST", "/app-bridge/capabilities"): "control_phone_app_capabilities",
    ("POST", "/intent/dispatch"): "control_phone_intent_dispatch",
    ("GET", "/ai/model/status"): "control_phone_ai_model_status",
    ("POST", "/ai/jobs/submit"): "control_phone_ai_submit",
    ("POST", "/ai/jobs/status"): "control_phone_ai_job",
    ("POST", "/ai/jobs/cancel"): "control_phone_ai_cancel",
    ("POST", "/app-bridge/invoke"): "control_phone_app_invoke",
    ("POST", "/app-bridge/operation"): "control_phone_app_operation",
    ("GET", "/diagnostics/logcat"): "control_phone_own_logcat",
    ("GET", "/diagnostics/exit-history"): "control_phone_exit_history",
    ("POST", "/diagnostics/events"): "control_phone_diagnostic_events",
    ("GET", "/diagnostics/security"): "control_phone_security_status",
    ("GET", "/diagnostics/permissions"): "control_phone_permission_matrix",
    ("GET", "/diagnostics/vpn"): "control_phone_vpn_status",
    ("GET", "/network/status"): "control_phone_network_status",
    ("GET", "/github-bridge/status"): "control_phone_bridge_status",
    ("GET", "/performance/status"): "control_phone_performance_status",
    ("POST", "/performance/mode"): "control_phone_performance_mode",
    ("POST", "/performance/optimize"): "control_phone_performance_optimize",
    ("GET", "/observation/status"): "control_phone_observation_status",
    ("GET", "/observation/events"): "control_phone_observation_events",
    ("GET", "/observation/frame"): "control_phone_observation_frame",
    ("GET", "/observation/timeline"): "control_phone_observation_timeline",
    ("GET", "/continuation/status"): "control_phone_continuation_status",
    ("POST", "/continuation/queue"): "control_phone_continuation_queue",
    ("POST", "/continuation/dispatch"): "control_phone_continuation_dispatch",
    ("POST", "/continuation/ack"): "control_phone_continuation_ack",
    ("POST", "/continuation/cancel"): "control_phone_continuation_cancel",
    ("GET", "/cycles/status"): "control_phone_cycle_status",
    ("GET", "/voice/status"): "control_phone_voice_status",
    ("GET", "/voice/settings"): "control_phone_voice_settings",
    ("POST", "/voice/settings"): "control_phone_voice_configure",
    ("POST", "/voice/enable"): "control_phone_voice_enable",
    ("POST", "/voice/stop"): "control_phone_voice_stop",
    ("POST", "/voice/question"): "control_phone_voice_question",
    ("POST", "/voice/ack"): "control_phone_voice_ack",
    ("POST", "/voice/command"): "control_phone_voice_command",
    ("POST", "/voice/say"): "control_phone_voice_say",
    ("POST", "/input"): "control_phone_input",
    ("POST", "/chat/direct"): "control_phone_chat_direct",
    ("POST", "/chat/new"): "control_phone_chat_new",
}


class LocalPhoneRequest(BaseModel):
    path: str = Field(min_length=1, max_length=180)
    method: Literal["GET", "POST"] = "GET"
    payload: dict | None = None
    timeout_seconds: float = Field(default=5.0, ge=0.5, le=22.0)


def validate_transfer_arguments(path: str, args: dict):
    def invalid():
        raise HTTPException(422,detail={"state":"invalid_transfer_arguments","dispatched":False})
    if path=="/transfer/start":
        name,size,digest=args.get("name"),args.get("size"),args.get("sha256")
        if (set(args)!={"name","size","sha256"} or not isinstance(name,str) or
            not 1<=len(name)<=180 or name.startswith(".") or
            any(c in name for c in ("/","\\",":")) or any(ord(c)<32 or ord(c)==127 for c in name) or
            type(size) is not int or not 0<=size<=2*1024**3 or
            not isinstance(digest,str) or not re.fullmatch("[a-f0-9]{64}",digest)):
            invalid()
        return
    identity=args.get("transfer_id")
    if not isinstance(identity,str) or not re.fullmatch("[A-Za-z0-9_-]{8,64}",identity):
        invalid()
    if path!="/transfer/chunk":
        if set(args)!={"transfer_id"}:invalid()
        return
    offset,data=args.get("offset"),args.get("data")
    if (set(args)!={"transfer_id","offset","data"} or type(offset) is not int or
        not 0<=offset<2*1024**3 or not isinstance(data,str) or not 1<=len(data)<=699052):
        invalid()
    try: decoded=base64.b64decode(data,validate=True)
    except (ValueError,binascii.Error):invalid()
    if not 1<=len(decoded)<=512*1024 or offset+len(decoded)>2*1024**3:invalid()


def resolved_tool(method: str, path: str, payload: dict | None) -> tuple[str, dict]:
    if method == "GET" and payload:
        raise HTTPException(400, detail={"state": "invalid_arguments", "dispatched": False})
    if re.fullmatch(r"/observation/frame/frame-[0-9]{10,15}\.jpg", path) and method == "GET":
        return "control_phone_observation_get_frame", {"frame_id": path.rsplit("/", 1)[-1]}
    tool = ROUTES.get((method, path))
    if tool is None:
        raise HTTPException(404, detail={"state": "unsupported_route", "dispatched": False})
    args = payload or {}
    if path.startswith("/transfer/"):
        # Larger payloads are exclusively allowed for bounded transfer chunks;
        # every existing non-transfer RPC retains its original 8KiB ceiling.
        validate_transfer_arguments(path,args)
        return tool,args
    if len(json.dumps(args, ensure_ascii=False)) > 8192:
        raise HTTPException(413, detail={"state": "arguments_too_large", "dispatched": False})
    return tool, args


@router.post("/phone/rpc")
async def local_phone_rpc(data: LocalPhoneRequest, request: Request):
    # The listener is already bound to 127.0.0.1; defend in depth here.
    if request.client is None or request.client.host not in ("127.0.0.1", "::1"):
        raise HTTPException(403, detail={"state": "local_only", "dispatched": False})
    registered = load_registered_phone()
    token = registered.get("token") if isinstance(registered, dict) else None
    header = request.headers.get("authorization", "")
    candidate = header[7:] if header.startswith("Bearer ") else ""
    if not isinstance(token, str) or not token or not hmac.compare_digest(candidate, token):
        raise HTTPException(401, detail={"state": "unauthorized", "dispatched": False})
    tool, args = resolved_tool(data.method, data.path, data.payload)
    if not connected():
        raise HTTPException(503, detail={"state": "no_session", "dispatched": False})
    rpc = {
        "jsonrpc": "2.0", "id": secrets.token_hex(12),
        "method": "tools/call", "params": {"name": tool, "arguments": args},
    }
    try:
        answer = await invoke(rpc, timeout=data.timeout_seconds)
    except ConnectionError as exc:
        # invoke() only raises ConnectionError if there was no session before dispatch.
        raise HTTPException(503, detail={"state": "no_session", "dispatched": False}) from exc
    except DirectPhoneUncertain as exc:
        raise HTTPException(504, detail={"state": "outcome_unknown", "dispatched": True}) from exc
    except Exception as exc:
        raise HTTPException(503, detail={"state": "relay_error", "dispatched": True,
                                         "error_type": type(exc).__name__}) from exc
    if answer.get("error") is not None:
        # Android policy/permission/tool errors are genuine answers; never
        # reinterpret them as evidence that the WSS path is unavailable.
        error = answer.get("error")
        reason = error.get("message", "Native tool failed") if isinstance(error, dict) else "Native tool failed"
        raise HTTPException(424, detail={"state": "phone_tool_error", "dispatched": True,
                                         "reason": str(reason)[:240]})
    result = answer.get("result")
    content = result.get("content") if isinstance(result, dict) else None
    if not isinstance(content, list) or len(content) != 1 or not isinstance(content[0], dict):
        raise HTTPException(502, detail={"state": "invalid_native_result", "dispatched": True})
    part = content[0]
    if part.get("type") == "image":
        if part.get("mimeType") != "image/jpeg" or not isinstance(part.get("data"), str):
            raise HTTPException(502, detail={"state": "invalid_image", "dispatched": True})
        return {"kind": "image/jpeg", "data": part["data"]}
    if part.get("type") != "text" or not isinstance(part.get("text"), str):
        raise HTTPException(502, detail={"state": "invalid_text", "dispatched": True})
    try:
        value = json.loads(part["text"])
    except json.JSONDecodeError:
        value = {"text": part["text"]}
    return {"kind": "json", "value": value, "transport": "native_wss"}
