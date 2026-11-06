"""Control's phone-first private relay, voice and checkpoint cycle contracts.

These are source/API tests. Android 17 microphone and cellular execution must
still be independently observed on the phone after an owner-approved update.
"""
import httpx
import pytest
from fastapi.testclient import TestClient
from pathlib import Path

from asterion_remote import mcp_gateway, phone_cloud_relay, native_routes, mcp_protocol


def test_cloud_routes_are_allowlisted_and_are_private_phone_tools():
    assert phone_cloud_relay.route_for("control_phone_cycle_start")=="phone_cycle_start"
    assert phone_cloud_relay.route_for("control_phone_voice_ack")=="phone_voice_ack"
    assert phone_cloud_relay.route_for("control_phone_network_status")=="phone_network_status"
    assert phone_cloud_relay.route_for("control_phone_screen") == "phone_screen"
    assert phone_cloud_relay.route_for("control_phone_observation_frame") == "phone_observation_frame"
    for name in ("control_phone_file_read","remote_pc_command",
                 "control_phone_anything"):
        with pytest.raises(ValueError):
            phone_cloud_relay.route_for(name)


def test_cloud_id_cannot_traverse_private_repository():
    valid="phone-"+"a"*32
    assert phone_cloud_relay.url("commands",valid).endswith(
        "/commands/android/"+valid+".json")
    for name in ("../private","phone-../../", "phone-"+"z"*32):
        with pytest.raises(ValueError):
            phone_cloud_relay.url("results",name)


def test_real_endpoint_schemas_are_validation_bounded():
    data={
        "project":"Asterion-Control",
        "checkpoint_id":"checkpoint-001",
        "priority_tier":"7*",
        "spec_reference":"7STAR_FROZEN_MASTER.md",
        "message":"Continue the existing project",
    }
    cycle=native_routes.CycleRequest(
        **data,cycle_id="cycle-20261106",
        conversation="same",max_cycles=7)
    assert cycle.max_cycles==7
    assert native_routes.VoiceQuestion(
        text="Are you there?",question_id="voice-007").question_id=="voice-007"
    assert native_routes.VoiceAcknowledgment(question_id="voice-007").question_id=="voice-007"
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        native_routes.CycleRequest(**data,cycle_id="x",max_cycles=-1)
    with pytest.raises(ValidationError):
        native_routes.VoiceQuestion(text="z"*701)


def test_mcp_catalog_exposes_away_from_home_and_voice_and_cycles():
    catalog={spec["name"] for spec in mcp_protocol.TOOLS}
    assert {
        "control_phone_network_status","control_phone_voice_ack",
        "control_phone_cycle_status","control_phone_cycle_start",
        "control_phone_cycle_pause","control_phone_cycle_resume",
        "control_phone_cycle_stop","control_phone_cycle_confirm_new_chat",
    }.issubset(catalog)


def test_phone_https_cloud_fallback_when_local_wifi_is_unavailable(monkeypatch):
    monkeypatch.setattr(mcp_gateway,"_secret",lambda p:"K"*48)
    monkeypatch.setattr(mcp_gateway,"_phone_route",
                        lambda:("http://192.168.1.116:8973/mcp","X"*48))
    monkeypatch.setattr(mcp_gateway,"_windows_route",lambda:None)
    async def unreachable(*args,**kwargs):
        raise httpx.ConnectError("Private Wi-Fi address unreachable")
    monkeypatch.setattr(mcp_gateway,"_forward",unreachable)
    observed=[]
    async def remote(name, arguments, mid):
        observed.append((name,arguments,mid))
        return {"jsonrpc":"2.0","id":mid,
                "result":{"content":[{"type":"text","text":"{\"network\":\"cellular\"}"}]}}
    monkeypatch.setattr(phone_cloud_relay,"submit",remote)
    headers={"Authorization":"Bearer "+"K"*48,
             "Accept":"application/json, text/event-stream"}
    with TestClient(mcp_gateway.app) as client:
        res=client.post("/mcp",headers=headers,json={
            "jsonrpc":"2.0","id":33,"method":"tools/call",
            "params":{"name":"control_phone_network_status","arguments":{}}})
        assert res.status_code==200
        assert res.json()["result"]["content"][0]["text"]=='{"network":"cellular"}'
        assert observed==[("control_phone_network_status",{},33)]


def test_voice_routes_dispatch_directly_to_authorized_android(monkeypatch):
    visited=[]
    monkeypatch.setattr(native_routes,"request",
        lambda path, method='GET', payload=None, timeout=5:
            type("Reply",(),{"json":lambda self:
                visited.append((path,method,payload)) or {"ok":True}})())
    native_routes.phone_voice_ack(native_routes.VoiceAcknowledgment(question_id="voice-007"))
    native_routes.phone_cycle_status()
    native_routes.phone_network_status()
    assert visited[0][0]=="/voice/ack"
    assert visited[1][0]=="/cycles/status"
    assert visited[2][0]=="/network/status"


def test_android_source_enforces_cellular_https_and_expiring_commands():
    root=Path(__file__).resolve().parents[1]
    a=(root/"android/app/src/main/java/com/asterion/control/PhoneGitBridge.java").read_text()
    n=(root/"android/app/src/main/java/com/asterion/control/TransportConnectivity.java").read_text()
    c=(root/"android/app/src/main/java/com/asterion/control/ContinuationCycle.java").read_text()
    assert "HttpsURLConnection" in a
    assert "expires_at_ms" in a and "status\",\"expired" in a
    assert "TRANSPORT_CELLULAR" in n and "TRANSPORT_VPN" in n
    assert "allowAutomaticDispatch" in c
    assert "confirmNewChat" in c
