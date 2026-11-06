"""OAuth-authorized tool discovery is independent of device connectivity."""
from fastapi.testclient import TestClient
from asterion_remote import mcp_gateway

def test_chatgpt_can_scan_protected_tool_schemas_without_connecting_devices(monkeypatch):
    monkeypatch.setattr(mcp_gateway,"_secret",lambda _: "k"*48)
    monkeypatch.setattr(mcp_gateway,"phone_live_connected",lambda:False)
    monkeypatch.setattr(mcp_gateway,"_phone_route",lambda:None)
    monkeypatch.setattr(mcp_gateway,"_windows_route",lambda:None)
    client=TestClient(mcp_gateway.app)
    anon={"accept":"application/json, text/event-stream"}
    authorized={**anon,"authorization":"Bearer "+("k"*48)}
    def rpc(method,headers,params=None):
        return client.post("/mcp",headers=headers,json={
            "jsonrpc":"2.0","id":1,"method":method,"params":params or {}})
    unauth=rpc("initialize",anon)
    assert unauth.status_code==401
    assert "resource_metadata" in unauth.headers["www-authenticate"]
    startup=rpc("initialize",authorized)
    assert startup.status_code==200
    assert startup.json()["result"]["serverInfo"]["name"]=="asterion-control"
    listing=rpc("tools/list",authorized)
    assert listing.status_code==200
    tools=listing.json()["result"]["tools"]
    assert len(tools)>=25
    assert any(t["name"]=="control_phone_voice_question" for t in tools)
    assert all(t["_meta"]["securitySchemes"]==[
        {"type":"oauth2","scopes":["asterion.control"]}
    ] for t in tools)
    protected=rpc("tools/call",anon,
        {"name":"control_phone_status","arguments":{}})
    assert protected.status_code==401
    assert "resource_metadata" in protected.headers["www-authenticate"]
