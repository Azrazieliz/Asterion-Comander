"""Asterion Control authenticated MCP-only gateway.

The gateway is an HTTPS tunnel ingress, not an AI or an application engine.
Prefer the already paired Samsung's native MCP endpoint for phone operations;
preserve optional Windows Control tools through its distinct local agent.
Android still needs an independent, stable HTTPS ingress before Windows can go.
"""
from __future__ import annotations

import asyncio
import hmac
import ipaddress
import json
import os
from urllib.parse import urlsplit
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

from .oauth_bridge import router as oauth_router, valid_access, challenge, SCOPE
from .phone_bridge import load as load_phone
from .phone_live import (router as phone_live_router, connected as phone_live_connected,
                         invoke as phone_live_invoke, DirectPhoneUncertain)
from .live_operator_bridge import OPERATOR as live_operator, LiveOperatorUnavailable

ROOT = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "AsterionControl"
GATEWAY_KEY = ROOT / "mcp-gateway-token.txt"
WINDOWS_AGENT_KEY = ROOT / "control-token.txt"
# The Windows worker is optional; Android-only MCP must start without it.
# Never pin the route to a single private router's DHCP address.
WINDOWS_UPSTREAM = os.environ.get("ASTERION_CONTROL_UPSTREAM", "")
NATIVE_PHONE_PREFIXES = (
    "control_phone_status",
    "control_phone_direct_status",
    "control_phone_bridge_status",
    "control_phone_health",
    "control_phone_performance_",
    "control_phone_screen",
    "control_phone_ui",
    "control_phone_input",
    "control_phone_apps",
    "control_phone_app_launch",
    "control_phone_chat_new",
    "control_phone_continuation_",
    "control_phone_observation_",
    "control_phone_voice_",
    "control_phone_cycle_",
    "control_phone_network_status",
)
LIVE_OPERATOR_TOOLS = [
    {"name":"control_live_ui",
     "description":"DEFAULT interactive phone control: inspect current Android accessibility state over the persistent authenticated direct WebSocket; returns one-use state_id. Call before every action.",
     "inputSchema":{"type":"object","properties":{},"required":[]}},
    {"name":"control_live_action",
     "description":"Execute ONE real native Android gesture via persistent direct WebSocket, guarded by the state_id returned by control_live_ui. Inspect again after this acknowledgment to confirm the resulting UI. Never run a prewritten action chain.",
     "inputSchema":{"type":"object","properties":{
         "state_id":{"type":"string","minLength":12},
         "action":{"type":"string","enum":["tap","swipe","long_press","back","home","recents","notifications","type","click_text"]},
         "x":{"type":"integer"},"y":{"type":"integer"},
         "x2":{"type":"integer"},"y2":{"type":"integer"},
         "duration_ms":{"type":"integer","minimum":100,"maximum":5000},
         "text":{"type":"string","maxLength":2000}
       },"required":["state_id","action"]}},
    {"name":"control_live_launch",
     "description":"Request opening an installed app through owner-approved Asterion Control while it is foreground. Requires fresh control_live_ui state_id; verify newly foreground app by inspecting again.",
     "inputSchema":{"type":"object","properties":{
         "state_id":{"type":"string","minLength":12},
         "package":{"type":"string","minLength":3,"maxLength":180}
       },"required":["state_id","package"]}},
]
LIVE_NAMES={tool["name"] for tool in LIVE_OPERATOR_TOOLS}

MAX_REQUEST = 2_000_000
MAX_RESPONSE = 8_000_000
app = FastAPI(
    title="Asterion Control MCP-only gateway", docs_url=None,
    redoc_url=None, openapi_url=None
)
app.include_router(phone_live_router)
app.include_router(oauth_router)

def _secret(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"MCP gateway credential unavailable: {path.name}") from exc
    if len(value) < 43:
        raise RuntimeError("MCP gateway bearer credential is too short")
    return value

def _phone_route():
    pairing = load_phone()  # already restricted to a private IPv4/IPv6 or VPN IP
    if not pairing:
        return None
    return pairing["base_url"] + "/mcp", pairing["token"]

def _validate_windows_route(url: str) -> str:
    parsed = urlsplit(url)
    try:
        ip = ipaddress.ip_address(parsed.hostname or "")
        port = parsed.port
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Invalid native Control agent route") from exc
    cgnat = ip in ipaddress.ip_network("100.64.0.0/10")
    if (parsed.scheme != "http" or port != 8911 or
        parsed.path != "/mcp" or parsed.query or parsed.fragment or
        parsed.username or parsed.password or
        ip.is_unspecified or ip.is_multicast or ip.is_link_local or
        not (ip.is_private or ip.is_loopback or cgnat)):
        raise RuntimeError("Windows MCP route must use a private Control IP")
    host = "[" + str(ip) + "]" if ip.version == 6 else str(ip)
    return "http://" + host + ":8911/mcp"

def _windows_route():
    if WINDOWS_UPSTREAM:
        url = _validate_windows_route(WINDOWS_UPSTREAM)
    else:
        try:
            private_host = (ROOT / "agent-host.txt").read_text(encoding="utf-8").strip()
            url = _validate_windows_route(private_host + "/mcp")
        except (RuntimeError, OSError):
            return None
    try:
        token = _secret(WINDOWS_AGENT_KEY)
    except RuntimeError:
        return None
    return url, token

@app.on_event("startup")
def verify_gateway():
    _secret(GATEWAY_KEY)
    # Explicit custom upstreams are validated, but Windows is not mandatory.
    if WINDOWS_UPSTREAM:
        _validate_windows_route(WINDOWS_UPSTREAM)

async def _forward(route, payload: bytes, request_headers: dict):
    url, token = route
    headers = {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    for key in ("mcp-protocol-version", "mcp-session-id"):
        value = request_headers.get(key)
        if value:
            headers[key] = value
    async with httpx.AsyncClient(
        timeout=20.0, trust_env=False, follow_redirects=False
    ) as client:
        response = await client.post(url, content=payload, headers=headers)
    if len(response.content) > MAX_RESPONSE:
        raise HTTPException(502, "MCP upstream exceeded response limit")
    return response

def _response(upstream):
    extra = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
    if sid := upstream.headers.get("mcp-session-id"):
        extra["Mcp-Session-Id"] = sid
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json"),
        headers=extra,
    )

def _tool_is_native(name: str):
    return name in NATIVE_PHONE_PREFIXES or any(
        name.startswith(prefix) for prefix in NATIVE_PHONE_PREFIXES
        if prefix.endswith("_")
    )

async def _preferred(payload: bytes, headers: dict, phone_first=True):
    candidates = []
    if phone_first:
        if paired := _phone_route():
            candidates.append(paired)
        try:
            if route := _windows_route():
                candidates.append(route)
        except RuntimeError:
            pass
    else:
        try:
            if route := _windows_route():
                candidates.append(route)
        except RuntimeError:
            pass
        if paired := _phone_route():
            candidates.append(paired)
    for route in candidates:
        try:
            response = await _forward(route, payload, headers)
            if response.status_code in (200, 202):
                return response
        except httpx.HTTPError:
            continue
    raise HTTPException(503, "No authorized native Control MCP upstream reachable")

@app.post("/mcp")
async def rpc(req: Request):
    # MCP authorization must challenge *all* unauthorized requests, including
    # initialize and tools/list. Otherwise clients can skip OAuth discovery and
    # a registered connection may produce an empty tool catalogue.
    bearer = req.headers.get("authorization", "")
    token = bearer[7:] if bearer.startswith("Bearer ") else ""
    if not token or not (
        hmac.compare_digest(token.encode(), _secret(GATEWAY_KEY).encode())
        or valid_access(token)
    ):
        raise HTTPException(
            401, "Asterion Control authorization required",
            headers={"WWW-Authenticate": challenge()},
        )
    accepted = req.headers.get("accept", "")
    if "application/json" not in accepted or "text/event-stream" not in accepted:
        raise HTTPException(406, "MCP requires JSON and event-stream Accept")
    try:
        length = int(req.headers.get("content-length") or "0")
    except ValueError:
        raise HTTPException(400, "Malformed content length")
    if length > MAX_REQUEST:
        raise HTTPException(413, "MCP request too large")
    payload = await req.body()
    if len(payload) > MAX_REQUEST:
        raise HTTPException(413, "MCP request too large")
    try:
        message = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError):
        raise HTTPException(400, "Invalid JSON-RPC body")
    if not isinstance(message, dict):
        raise HTTPException(400, "A single MCP JSON-RPC object is required")
    method = message.get("method")
    # The MCP client sends this notification after successful initialize.
    # It has no JSON-RPC id, so a stateless server acknowledges it with 202.
    if method == "notifications/initialized":
        return Response(status_code=202, headers={"Cache-Control":"no-store"})
    name = (message.get("params") or {}).get("name") if isinstance(message.get("params"), dict) else ""
    if method == "tools/call":
        params = message.get("params") or {}
        if name in LIVE_NAMES:
            arguments=params.get("arguments") or {}
            if not isinstance(arguments,dict):
                raise HTTPException(400,"Live Control arguments must be an object")
            route=_windows_route()
            if route is None:
                raise HTTPException(503,"Private Windows Control server is unavailable")
            try:
                if name=="control_live_ui":
                    live_result=await live_operator.inspect(route)
                elif name=="control_live_action":
                    live_result=await live_operator.action(route,arguments)
                else:
                    live_result=await live_operator.launch(route,arguments)
            except LiveOperatorUnavailable as exc:
                # No automatic retry: a dispatched gesture might have executed.
                raise HTTPException(504,str(exc)) from exc
            result={
                "content":[{"type":"text","text":json.dumps(live_result,
                                                            ensure_ascii=False)}],
                "structuredContent":live_result,
                "isError":not bool(live_result.get("ok")),
            }
            return Response(content=json.dumps({"jsonrpc":"2.0",
                                                "id":message.get("id"),
                                                "result":result}),
                            media_type="application/json",
                            headers={"Cache-Control":"no-store"})
        native = isinstance(name, str) and _tool_is_native(name)
        if native:
            if phone_live_connected():
                try:
                    # A dispatched WSS call is never silently repeated after
                    # timeout/disconnect, even if the phone's final result is lost.
                    answer = await phone_live_invoke(message)
                    return Response(content=json.dumps(answer), media_type="application/json",
                                    headers={"Cache-Control": "no-store"})
                except (DirectPhoneUncertain, asyncio.TimeoutError):
                    raise HTTPException(504, "Direct Android MCP outcome uncertain; never replay")
                except (ConnectionError, RuntimeError, ValueError):
                    raise HTTPException(503, "Direct Android MCP session unavailable")
            # When both devices are on trusted private Wi-Fi, use the existing
            # native Android MCP route directly. No GitHub cloud polling.
            if paired := _phone_route():
                try:
                    direct = await asyncio.wait_for(_forward(paired, payload, req.headers),
                                                    timeout=4.0)
                    if direct.status_code == 200:
                        return _response(direct)
                    if direct.status_code in (401, 403):
                        raise HTTPException(503, "Native Android pairing rejected")
                    raise HTTPException(504,
                        "Native Android MCP returned uncertain status; no replay")
                except (httpx.ConnectError, httpx.ConnectTimeout):
                    raise HTTPException(503, "Android direct route unavailable")
                except (asyncio.TimeoutError, httpx.ReadTimeout, httpx.RemoteProtocolError):
                    raise HTTPException(504, "Android command outcome uncertain; no replay")
            raise HTTPException(503,
                "Android direct TLS connection not attached; enable Control on the phone")
        upstream = await _preferred(payload, req.headers, phone_first=False)
        return _response(upstream)
    if method == "tools/list":
        # Merge the phone and optional Windows tool catalogues. A phone-owned
        # tool name wins over its older Windows proxy with the same name.
        catalogs = []
        if phone_live_connected():
            try:
                catalogs.append(await phone_live_invoke(message, timeout=10.0))
            except (DirectPhoneUncertain, ConnectionError, RuntimeError, ValueError):
                pass
        for route in (() if catalogs else (_phone_route(),)):
            if route is None:
                continue
            try:
                response = await _forward(route, payload, req.headers)
                if response.status_code == 200:
                    catalogs.append(json.loads(response.content))
            except (httpx.HTTPError, ValueError):
                pass
        try:
            route = _windows_route()
            if route is not None:
                response = await _forward(route, payload, req.headers)
                if response.status_code == 200:
                    catalogs.append(json.loads(response.content))
        except (RuntimeError, httpx.HTTPError, ValueError):
            pass
        # Canonical tools are discoverable even while Android or a subordinate
        # Windows agent is older/offline. Native tools override their schemas.
        # Discovery is NOT evidence that a device command can execute.
        from .mcp_protocol import TOOLS
        catalogs.append({"result":{"tools":TOOLS+LIVE_OPERATOR_TOOLS}})
        merged = {}
        # Reverse so live native catalogues win over the static baseline.
        for item in reversed(catalogs):
            for spec in item.get("result", {}).get("tools", []):
                if isinstance(spec, dict) and isinstance(spec.get("name"), str):
                    merged[spec["name"]] = spec
        # OAuth discovery for ChatGPT, while preserving the original tool
        # catalogues, names, argument schemas, and native routing behavior.
        tools = []
        for spec in merged.values():
            tagged = dict(spec)
            tagged["_meta"] = {
                **(tagged.get("_meta") or {}),
                "securitySchemes": [{"type": "oauth2", "scopes": [SCOPE]}],
            }
            tools.append(tagged)
        response = {
            "jsonrpc": "2.0", "id": message.get("id"),
            "result": {"tools": tools},
        }
        return Response(content=json.dumps(response), media_type="application/json",
                        headers={"Cache-Control": "no-store"})
    if method == "initialize":
        return Response(content=json.dumps({
            "jsonrpc":"2.0","id":message.get("id"),
            "result":{"protocolVersion":"2025-11-25",
                      "capabilities":{"tools":{}},
                      "serverInfo":{"name":"asterion-control","version":"0.9.0"}}
        }),media_type="application/json",headers={"Cache-Control":"no-store"})
    if method == "ping":
        return Response(content=json.dumps({
            "jsonrpc":"2.0","id":message.get("id"),"result":{}
        }),media_type="application/json",headers={"Cache-Control":"no-store"})
    return _response(await _preferred(payload, req.headers, phone_first=True))

@app.get("/mcp")
@app.delete("/mcp")
async def no_sse():
    return Response(status_code=405, headers={"Allow": "POST"})

@app.get("/healthz")
def health():
    return {"service": "asterion-control-mcp-gateway", "ok": True, "version": 2}
