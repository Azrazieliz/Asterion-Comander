"""Gateway routes native phone tools to Android, optional PC tools to Windows."""
import json
import httpx
from fastapi.testclient import TestClient
from asterion_remote import mcp_gateway

HEADERS={
    "Authorization":"Bearer "+"A"*48,
    "Accept":"application/json, text/event-stream",
    "Content-Type":"application/json",
}

def test_phone_primary_catalog_merge_and_tool_routing(monkeypatch):
    monkeypatch.setattr(mcp_gateway,"_secret",lambda path:"A"*48)
    monkeypatch.setattr(mcp_gateway,"_phone_route",
                        lambda:("http://192.168.1.7:8973/mcp","P"*48))
    monkeypatch.setattr(mcp_gateway,"_windows_route",
                        lambda:("http://127.0.0.1:8911/mcp","W"*48))
    observed=[]
    async def fake_forward(route,payload,headers):
        message=json.loads(payload)
        is_phone="8973" in route[0]
        observed.append(("phone" if is_phone else "windows",message["method"]))
        if message["method"]=="tools/list":
            names=["control_phone_status","control_phone_apps"] if is_phone else [
                "control_phone_status","remote_pc_input"]
            specs=[{"name":name,"description":"Android" if is_phone else "Windows",
                    "inputSchema":{"type":"object","properties":{}}} for name in names]
            return httpx.Response(200,json={"jsonrpc":"2.0","id":1,
                                            "result":{"tools":specs}})
        return httpx.Response(200,json={
            "jsonrpc":"2.0","id":1,
            "result":{"content":[{"type":"text",
                "text":"phone" if is_phone else "windows"}]}})
    monkeypatch.setattr(mcp_gateway,"_forward",fake_forward)
    with TestClient(mcp_gateway.app) as client:
        unauthorized=client.post("/mcp",headers={
            **HEADERS,"Authorization":"Bearer invalid"},json={
            "jsonrpc":"2.0","id":1,"method":"tools/list"})
        assert unauthorized.status_code==401
        catalog=client.post("/mcp",headers=HEADERS,json={
            "jsonrpc":"2.0","id":1,"method":"tools/list"})
        assert catalog.status_code==200
        byname={s["name"]:s for s in catalog.json()["result"]["tools"]}
        assert byname["control_phone_status"]["description"]=="Android"
        assert byname["remote_pc_input"]["description"]=="Windows"
        assert mcp_gateway._tool_is_native("control_phone_chat_new")
        phone=client.post("/mcp",headers=HEADERS,json={
            "jsonrpc":"2.0","id":1,"method":"tools/call",
            "params":{"name":"control_phone_apps","arguments":{}}})
        assert phone.json()["result"]["content"][0]["text"]=="phone"
        windows=client.post("/mcp",headers=HEADERS,json={
            "jsonrpc":"2.0","id":1,"method":"tools/call",
            "params":{"name":"remote_pc_input","arguments":{"action":"move"}}})
        assert windows.json()["result"]["content"][0]["text"]=="windows"
    assert observed[-2:]==[("phone","tools/call"),("windows","tools/call")]

def test_phone_only_gateway_still_serves_native_tools(monkeypatch):
    monkeypatch.setattr(mcp_gateway,"_secret",lambda path:"A"*48)
    monkeypatch.setattr(mcp_gateway,"_phone_route",
                        lambda:("http://192.168.1.7:8973/mcp","P"*48))
    def no_windows():
        raise RuntimeError("Windows worker intentionally offline")
    monkeypatch.setattr(mcp_gateway,"_windows_route",no_windows)
    async def phone(route,payload,headers):
        assert "8973" in route[0]
        return httpx.Response(200,json={"jsonrpc":"2.0","id":55,
          "result":{"content":[{"type":"text","text":"android-native"}]}})
    monkeypatch.setattr(mcp_gateway,"_forward",phone)
    with TestClient(mcp_gateway.app) as client:
        response=client.post("/mcp",headers=HEADERS,json={
          "jsonrpc":"2.0","id":55,"method":"tools/call",
          "params":{"name":"control_phone_status","arguments":{}}})
        assert response.status_code==200
        assert "android-native" in response.text
