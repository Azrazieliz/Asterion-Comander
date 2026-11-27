"""Regression: retired public OAuth/MCP surface must remain absent.

The original public tool-discovery endpoint was explicitly revoked.
The existing private GitHub fallback and authenticated native WSS remain.
"""
from fastapi.testclient import TestClient
from asterion_remote.native_phone_relay import app


def test_no_public_tool_discovery_or_oauth_gateway():
    routes={getattr(route,"path",None) for route in app.routes}
    assert "/healthz" in routes
    for forbidden in ("/mcp", "/oauth/authorize", "/oauth/token",
                      "/.well-known/oauth-protected-resource/mcp",
                      "/.well-known/oauth-authorization-server"):
        assert forbidden not in routes
    with TestClient(app) as client:
        # FastAPI may defer mounted routers; test the actual effective HTTP
        # surface, not only direct route objects. No valid or invalid input
        # may rediscover the retired public gateway.
        for path in ("/mcp", "/oauth/authorize", "/oauth/token",
                     "/.well-known/oauth-protected-resource/mcp",
                     "/.well-known/oauth-authorization-server"):
            assert client.get(path).status_code==404
            assert client.post(path,json={"method":"tools/list"}).status_code==404
        assert client.post("/phone/rpc",json={"path":"/health"}).status_code==403


def test_relay_health_never_claims_a_public_chatgpt_connector():
    with TestClient(app) as client:
        health=client.get("/healthz").json()
    assert health["service"]=="asterion-native-phone-wss"
    assert health.get("public_mcp_enabled") is not True
