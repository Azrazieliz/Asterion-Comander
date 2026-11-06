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
        result = phone.get("result", {})
        if result.get("isError") or phone.get("error"):
            print("LIVE_PHONE_ERROR=" + str(phone.get("error") or "MCP isError"))
        else:
            content = result.get("content", [])
            if content and content[0].get("type") == "text":
                try:
                    state = json.loads(content[0].get("text", ""))
                    for key in ("device", "version", "version_name", "ok", "paired",
                                "reachable", "direct_mcp_connected"):
                        if key in state:
                            print("PHONE_" + key.upper() + "=" + str(state[key]))
                    if isinstance(state.get("remote_transport"), dict):
                        direct = state["remote_transport"].get("direct_mcp", {})
                        print("PHONE_DIRECT_CONNECTED=" + str(direct.get("connected", False)).lower())
                except (ValueError, TypeError):
                    print("PHONE_STATUS_UNPARSEABLE=true")
    except (httpx.HTTPError, ValueError, RuntimeError):
        print("LIVE_PHONE_STATUS_RETURNED=false")

    # Read-only native checks, no configuration changes or raw credentials.
    for call_id, tool, prefix in (
        (5, "control_phone_direct_status", "DIRECT"),
        (6, "control_phone_network_status", "NETWORK"),
        (7, "control_phone_performance_status", "PERFORMANCE"),
        (8, "control_phone_voice_status", "VOICE"),
        (9, "control_phone_cycle_status", "CYCLE"),
    ):
        try:
            answer = rpc("tools/call", call_id, {"name": tool, "arguments": {}})
            result = answer.get("result", {})
            if result.get("isError") or answer.get("error"):
                print(prefix + "_LIVE_CALL=ERROR")
                continue
            content = result.get("content", [])
            parsed = (json.loads(content[0]["text"])
                      if content and content[0].get("type") == "text" else {})
            if not isinstance(parsed, dict):
                print(prefix + "_LIVE_CALL=INVALID_RESPONSE")
                continue
            print(prefix + "_LIVE_CALL=OK")
            if prefix == "DIRECT":
                for key in ("connected", "phase", "transport"):
                    if key in parsed: print("LIVE_PHONE_DIRECT_" + key.upper() + "=" + str(parsed[key]))
            if prefix == "NETWORK":
                for key in ("network", "validated", "requires_home_wifi"):
                    if key in parsed: print("LIVE_PHONE_NETWORK_" + key.upper() + "=" + str(parsed[key]))
            if prefix == "PERFORMANCE":
                for key in ("requested_mode", "reason", "capture_interval_ms",
                            "jpeg_quality", "observation_interval_ms",
                            "frames_encoded", "frames_skipped"):
                    if key in parsed: print("LIVE_PHONE_PERF_" + key.upper() + "=" + str(parsed[key]))
            if prefix in ("VOICE", "CYCLE"):
                print(prefix + "_REPORTED_STATUS=" + str(parsed.get("state",
                     parsed.get("status", "available")))[:80])
        except (httpx.HTTPError, ValueError, RuntimeError, TypeError) as exc:
            print(prefix + "_LIVE_CALL=UNAVAILABLE_" + type(exc).__name__)
