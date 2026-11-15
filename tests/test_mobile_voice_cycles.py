"""Phone-local voice/cycles and direct cellular MCP source contracts."""
from pathlib import Path

import pytest
from pydantic import ValidationError

from asterion_remote import native_routes, github_bridge, native_phone_relay


def test_voice_and_cycle_requests_remain_bounded():
    data = {
        "project": "Asterion-Control",
        "checkpoint_id": "checkpoint-001",
        "priority_tier": "7*",
        "spec_reference": "7STAR_FROZEN_MASTER.md",
        "message": "Continue the existing project",
    }
    cycle = native_routes.CycleRequest(
        **data, cycle_id="cycle-20261106", conversation="same", max_cycles=7)
    assert cycle.max_cycles == 7
    assert native_routes.VoiceQuestion(
        text="Are you there?", question_id="voice-007").question_id == "voice-007"
    assert native_routes.VoiceAcknowledgment(
        question_id="voice-007").question_id == "voice-007"
    with pytest.raises(ValidationError):
        native_routes.CycleRequest(**data, cycle_id="x", max_cycles=-1)
    with pytest.raises(ValidationError):
        native_routes.VoiceQuestion(text="z" * 701)


def test_private_bridge_lists_phone_voice_and_cycle_controls():
    operations=set(github_bridge.ALLOWED)|set(github_bridge.PHONE_NATIVE)
    assert {
        "phone_network_status", "phone_voice_ack", "phone_cycle_status",
        "phone_continuation_queue", "phone_continuation_dispatch",
        "phone_continuation_ack",
    }.issubset(operations)
    assert "phone_cycle_start" in operations


def test_existing_native_voice_and_cycles_dispatch_to_phone(monkeypatch):
    visited = []
    monkeypatch.setattr(
        native_routes, "request",
        lambda path, method="GET", payload=None, timeout=5:
            type("Reply", (), {"json": lambda self:
                visited.append((path, method, payload)) or {"ok": True}})())
    native_routes.phone_voice_ack(
        native_routes.VoiceAcknowledgment(question_id="voice-007"))
    native_routes.phone_cycle_status()
    native_routes.phone_network_status()
    assert [row[0] for row in visited] == [
        "/voice/ack", "/cycles/status", "/network/status"]


def test_phone_source_uses_direct_tls_and_phone_owned_cycles():
    root = Path(__file__).resolve().parents[1]
    src = root / "android/app/src/main/java/com/asterion/control"
    agent = (src / "AgentService.java").read_text()
    direct = (src / "PhoneDirectMcp.java").read_text()
    net = (src / "TransportConnectivity.java").read_text()
    cycles = (src / "ContinuationCycle.java").read_text()
    voice = (src / "VoiceDialogueService.java").read_text()
    assert "PhoneDirectMcp.start(this)" in agent
    assert "phoneBridgePoller.scheduleWithFixedDelay" in agent
    assert "PhoneGitBridge.poll(this)" in agent
    assert "phoneBridgePoller.shutdownNow()" in agent
    assert "cycles.tick()" not in agent
    assert "setEndpointIdentificationAlgorithm(\"HTTPS\")" in direct
    assert "sec-websocket-accept" in direct.lower()
    assert "Authorization: Bearer " in direct
    assert "String key=AgentService.token(owner)" in direct
    assert 'getSharedPreferences("control"' not in direct
    assert "TRANSPORT_CELLULAR" in net and "TRANSPORT_VPN" in net
    assert "cycles.tick()" not in agent and "cycleWorker" not in agent
    assert "allowAutomaticDispatch" in cycles
    assert "confirmNewChat" in cycles
    assert "speaker.speak" in voice and "SpeechRecognizer" in voice


def test_private_relay_has_no_callable_public_mcp_gateway():
    routes={getattr(item,"path",None) for item in native_phone_relay.app.routes}
    assert "/healthz" in routes
    assert "/mcp" not in routes
    assert "/oauth/authorize" not in routes
    source=(Path(__file__).resolve().parents[1]/
            "android/app/src/main/java/com/asterion/control/PhoneDirectMcp.java").read_text()
    assert "sec-websocket-accept" in source.lower()
