"""Read-only live MCP ingress and phone status check. Never print credentials."""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import httpx

state = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "AsterionControl"
url = (state / "mcp-stable-https-url.txt").read_text(encoding="utf-8").strip()
secret = (state / "mcp-gateway-token.txt").read_text(encoding="utf-8").strip()
p = urlsplit(url)
if (p.scheme != "https" or p.hostname != "wise-eagle-c8b55706.tunnl.gg" or
        p.path != "/mcp" or p.username or p.password or p.query or p.fragment or
        p.port is not None or len(secret) < 43):
    raise SystemExit("CONTROL_PUBLIC_MCP_CONFIG_INVALID")

headers = {"Authorization": "Bearer " + secret,
           "Accept": "application/json, text/event-stream",
           "Content-Type": "application/json"}
base = url.removesuffix("/mcp")

with httpx.Client(timeout=16, trust_env=False, follow_redirects=False) as client:
    def rpc(method: str, id: int, params=None):
        body = {"jsonrpc": "2.0", "id": id, "method": method}
        if params is not None:
            body["params"] = params
        res = client.post(url, json=body, headers=headers)
        if res.status_code != 200:
            raise RuntimeError("MCP " + method + " returned HTTP " + str(res.status_code))
        result = res.json()
        if result.get("id") != id:
            raise RuntimeError("Unexpected MCP response ID")
        return result

    init = rpc("initialize", 1, {
        "protocolVersion": "2025-11-25", "capabilities": {},
        "clientInfo": {"name": "asterion-connection-verifier", "version": "1.0"}
    })
    assert init.get("result", {}).get("serverInfo", {}).get("name") == "asterion-control"
    listed = rpc("tools/list", 2)
    names = {v.get("name") for v in listed.get("result", {}).get("tools", [])
             if isinstance(v, dict)}
    expected = {"control_phone_health", "control_phone_voice_question",
                "control_phone_cycle_status", "control_phone_performance_optimize",
                "control_pc_performance_mode"}
    if not expected.issubset(names):
        raise RuntimeError("Control MCP tool discovery missing active tools")
    unauth = client.post(url, json={
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "control_phone_health", "arguments": {}}
    }, headers={"Accept": "application/json, text/event-stream"})
    if unauth.status_code != 401:
        raise RuntimeError("Anonymous Control command was not rejected")
    oauth = client.get(base + "/.well-known/oauth-authorization-server")
    if oauth.status_code != 200 or oauth.json().get("issuer") != base:
        raise RuntimeError("Control OAuth discovery is not available")

    print("PUBLIC_MCP_AUTH_VERIFIED=true")
    print("PUBLIC_MCP_ANONYMOUS_DENIED=true")
    print("PUBLIC_MCP_OAUTH_DISCOVERY=true")
    print("PUBLIC_MCP_TOOL_COUNT=" + str(len(names)))

    try:
        phone = rpc("tools/call", 4, {
            "name": "control_phone_status", "arguments": {}
        })
        print("LIVE_PHONE_STATUS_RETURNED=" + str("result" in phone).lower())
    except (httpx.HTTPError, ValueError, RuntimeError):
        print("LIVE_PHONE_STATUS_RETURNED=false")
