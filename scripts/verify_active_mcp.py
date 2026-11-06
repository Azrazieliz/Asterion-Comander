"""Read-only end-to-end probe of Control's authenticated HTTPS MCP gateway.

No credentials are printed or stored outside existing private Control state.
This probes the owner's own Android and Windows agents through the Control MCP
transport. A working MCP gateway is NOT proof that ChatGPT installed the plugin.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import httpx

STATE = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "AsterionControl"
BASE = (STATE / "mcp-tunnel-url.txt").read_text("utf8").strip().rstrip("/")
KEY = (STATE / "mcp-gateway-token.txt").read_text("utf8").strip()
if len(KEY) < 43 or not BASE.startswith("https://") or not BASE.endswith(".trycloudflare.com"):
    raise RuntimeError("Native Control HTTPS tunnel is not initialized")
URL = BASE + "/mcp"
HEADERS = {"Authorization": "Bearer " + KEY,
           "Accept": "application/json, text/event-stream",
           "Content-Type": "application/json"}


def rpc(client: httpx.Client, method: str, id: int, params: dict | None = None) -> dict:
    payload = {"jsonrpc": "2.0", "id": id, "method": method}
    if params is not None:
        payload["params"] = params
    response = client.post(URL, headers=HEADERS, json=payload)
    response.raise_for_status()
    if response.headers.get("content-type", "").split(";")[0] != "application/json":
        raise RuntimeError("Unexpected Control MCP content type")
    result = response.json()
    if result.get("id") != id or result.get("error"):
        raise RuntimeError(f"Control MCP {method} was not accepted")
    return result.get("result", {})


with httpx.Client(timeout=20, trust_env=False, follow_redirects=False) as client:
    initialized = rpc(client, "initialize", 1,
                      {"protocolVersion": "2025-11-25",
                       "capabilities": {},
                       "clientInfo": {"name": "asterion-acceptance", "version": "1.0"}})
    if initialized.get("serverInfo", {}).get("name") not in (
        "asterion-control", "asterion-control-android"):
        raise RuntimeError("Wrong native Control MCP server")
    listing = rpc(client, "tools/list", 2)
    names = {item.get("name") for item in listing.get("tools", [])}
    if "control_phone_status" not in names or "remote_processes" not in names:
        raise RuntimeError("Native MCP catalogue missing phone or Windows capabilities")
    reply = rpc(client, "tools/call", 3,
                {"name": "control_phone_health", "arguments": {}})
    content = reply.get("content", [])
    health = json.loads(content[0]["text"]) if content and content[0].get("type") == "text" else {}
    if health.get("device") != "SM-S948B" or not health.get("ok"):
        raise RuntimeError("Samsung native MCP health result missing")
    print("CONTROL_HTTPS_MCP_VERIFIED=true")
    print("CONTROL_PHONE_HEALTH_VERIFIED=true")
    print("CONTROL_MCP_TOOL_COUNT=" + str(len(names)))
    print("CONTROL_MCP_PHONE=" + health["device"])
