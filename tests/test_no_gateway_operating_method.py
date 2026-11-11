"""Guard against reintroducing the retired MCP gateway or fake ChatGPT tool.

The existing authenticated Windows REST + native Android WSS + private GitHub
command/result bridge remain supported. The phone WSS relay MUST NOT expose
MCP tool discovery, OAuth or a generic HTTP tool proxy.
"""
from pathlib import Path
from fastapi.testclient import TestClient
from asterion_remote.native_phone_relay import app

ROOT=Path(__file__).resolve().parents[1]
WORKER=(ROOT/"asterion_remote"/"app.py").read_text(encoding="utf-8")
WATCHDOG=(ROOT/"scripts"/"control_repair_watchdog.ps1").read_text(encoding="utf-8")
WINDOWS=(ROOT/"scripts"/"start_windows.ps1").read_text(encoding="utf-8")
AGENT=(ROOT/"android/app/src/main/java/com/asterion/control/AgentService.java").read_text(encoding="utf-8")
METHOD=(ROOT/"README.md").read_text(encoding="utf-8")

def test_native_wss_relay_only_has_expected_routes():
    routes=[r.path for r in app.routes]
    assert "/phone/live" in routes
    assert "/healthz" in routes
    assert "/mcp" not in routes
    assert "/oauth/authorize" not in routes
    assert "/.well-known/oauth-protected-resource/mcp" not in routes
    assert "/docs" not in routes
    assert "/openapi.json" not in routes

def test_native_relay_reports_truthful_health():
    response=TestClient(app).get("/healthz")
    assert response.status_code==200
    payload=response.json()
    assert payload["service"]=="asterion-native-phone-wss"
    assert isinstance(payload["phone_connected"],bool)
    assert TestClient(app).post("/mcp",json={"method":"tools/list"}).status_code==404

def test_worker_does_not_mount_mcp():
    assert "include_router(mcp_setup_router)" not in WORKER
    assert "from . import mcp_protocol" not in WORKER
    assert "from .mcp_setup import router" not in WORKER

def test_android_control_has_no_mcp_http_endpoint():
    assert 'path.equals("/mcp")' not in AGENT
    assert 'path.equals("/health")' in AGENT

def test_watchdog_only_starts_native_relay():
    assert "asterion_remote.native_phone_relay:app" in WATCHDOG
    assert "asterion_remote.mcp_gateway:app" not in WATCHDOG
    assert "mcp-gateway-token.txt" not in WATCHDOG

def test_windows_supervisor_cannot_start_old_mcp_ssh():
    assert "start_persistent_ssh_mcp.py" not in WINDOWS
    assert "mcp-stable-ssh-enabled.flag" not in WINDOWS

def test_operating_method_forbids_callable_control_tool():
    assert "NOT a tool callable directly inside ChatGPT" in METHOD
    assert "Azrazieliz/Asterion-Control-Bridge" in METHOD
    assert "20 total ChatGPT messages" in METHOD
    assert "GitHub" in METHOD
