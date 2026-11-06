"""Phone-first continuation and game observation API contracts.

These tests do not substitute for Android-native UI, package or microphone tests.
"""
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from asterion_remote.app import app
from asterion_remote import mcp_protocol, native_routes

PAYLOAD = {
    "project": "Asterion-Game",
    "checkpoint_id": "phase7-checkpoint001",
    "priority_tier": "7*",
    "spec_reference": "7STAR_FROZEN_MASTER.md",
    "message": "Continue from the saved progress ledger without changing scope."
}

def test_continuation_and_observation_endpoints_require_auth():
    with TestClient(app) as client:
        for path in (
            "/api/v1/phone/continuation/status",
            "/api/v1/phone/observation/status",
            "/api/v1/phone/observation/events",
            "/api/v1/phone/observation/frame",
            "/api/v1/phone/voice/status",
            "/api/v1/phone/bridge/status",
            "/api/v1/phone/apps",
        ):
            assert client.get(path).status_code == 401
        assert client.post("/api/v1/phone/continuation/queue", json=PAYLOAD).status_code == 401
        assert client.post("/api/v1/phone/continuation/dispatch").status_code == 401
        assert client.post("/api/v1/phone/voice/question",json={"text":"Question"}).status_code == 401
        assert client.post("/api/v1/phone/apps/launch",json={"package":"com.gamepilot"}).status_code == 401
        assert client.post("/api/v1/phone/continuation/ack",json={"checkpoint_id":"abc","response_receipt":"observed next turn"}).status_code == 401

def test_checkpoint_requires_ranked_spec_and_safe_message():
    assert native_routes.ContinuationRequest(**PAYLOAD).priority_tier == "7*"
    with pytest.raises(ValidationError):
        native_routes.ContinuationRequest(**{**PAYLOAD, "priority_tier":"critical"})
    with pytest.raises(ValidationError):
        native_routes.ContinuationRequest(**{**PAYLOAD, "message":""})
    with pytest.raises(ValidationError):
        native_routes.ContinuationRequest(**{**PAYLOAD, "message":"x"*4000})

def test_mcp_lists_phone_continuation_and_game_observer():
    names={item["name"] for item in mcp_protocol.TOOLS}
    assert {
        "control_phone_continuation_status",
        "control_phone_continuation_queue",
        "control_phone_continuation_dispatch",
        "control_phone_observation_status",
        "control_phone_observation_events",
        "control_phone_observation_frame",
        "control_phone_voice_status",
        "control_phone_voice_question",
        "control_phone_bridge_status",
        "control_phone_apps",
        "control_phone_app_launch",
        "control_phone_continuation_ack",
        "control_phone_continuation_cancel"
    }.issubset(names)

def test_mcp_uses_native_authorized_routes(monkeypatch):
    monkeypatch.setattr(native_routes,"phone_continuation_queue",
                        lambda request:{"state":"queued","checkpoint_id":request.checkpoint_id})
    assert mcp_protocol.invoke_tool("control_phone_continuation_queue", PAYLOAD) == {
        "state":"queued","checkpoint_id":"phase7-checkpoint001"
    }
    monkeypatch.setattr(native_routes,"phone_observation_status",
                        lambda:{"enabled":True,"target":"com.asterion.game"})
    assert mcp_protocol.invoke_tool("control_phone_observation_status",{})["enabled"]

def test_generic_phone_app_catalog_launch_and_receipt_contract(monkeypatch):
    from asterion_remote import native_routes
    with pytest.raises(ValidationError):
        native_routes.AppLaunch(package="bad package")
    assert native_routes.AppLaunch(package="com.onemt.and.shoujokaisen").package
    with pytest.raises(ValidationError):
        native_routes.CheckpointAcknowledgment(checkpoint_id="abc", response_receipt="short")

    observed=[]
    monkeypatch.setattr(native_routes,"phone_app_launch",
        lambda req: observed.append(req.package) or {"intent_dispatched":True,"verified_foreground":False})
    result=mcp_protocol.invoke_tool("control_phone_app_launch",
        {"package":"com.onemt.and.shoujokaisen"})
    assert result["intent_dispatched"] and not result["verified_foreground"]
    assert observed==["com.onemt.and.shoujokaisen"]

    monkeypatch.setattr(native_routes,"phone_continuation_ack",
        lambda req:{"ok":True,"checkpoint_id":req.checkpoint_id,"state":"acknowledged"})
    response=mcp_protocol.invoke_tool("control_phone_continuation_ack",
        {"checkpoint_id":"checkpoint001","response_receipt":"observed-next-chat-turn-001"})
    assert response["state"]=="acknowledged"

def test_voice_question_schema_and_direct_native_dispatch(monkeypatch):
    assert native_routes.VoiceQuestion(text="What happened?",locale="en-US").text
    with pytest.raises(ValidationError):
        native_routes.VoiceQuestion(text="")
    with pytest.raises(ValidationError):
        native_routes.VoiceQuestion(text="x"*701)
    monkeypatch.setattr(native_routes,"phone_voice_question",
                        lambda question:{"ok":True,"question":question.text})
    assert mcp_protocol.invoke_tool("control_phone_voice_question",
                                    {"text":"What happened?","locale":"en-US"})["ok"]

def test_phone_private_bridge_diagnostics_never_return_credentials(monkeypatch):
    monkeypatch.setattr(native_routes,"phone_bridge_status",
        lambda:{"enabled":True,"token_present":True,"completed":3})
    state=mcp_protocol.invoke_tool("control_phone_bridge_status",{})
    assert state["enabled"] and state["completed"]==3
    assert "token" not in state
