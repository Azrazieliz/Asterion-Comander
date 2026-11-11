"""ChatGPT transport fallback must not leak keys or execute writes implicitly."""
from pathlib import Path
import importlib.util
import sys

ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/"scripts/chatgpt_control_transport.py"
spec=importlib.util.spec_from_file_location("asterion_control_transport",str(PATH))
bridge=importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)

def test_phone_status_and_network_are_safe_reads():
    assert {"control_phone_status","control_phone_network_status",
            "control_phone_direct_status"}.issubset(bridge.READ_ONLY)
    assert "control_phone_input" not in bridge.READ_ONLY
    assert "control_phone_voice_question" not in bridge.READ_ONLY

def test_payload_redacts_sensitive_fields():
    raw={"device":"SM-S948B","token":"do-not-show",
         "nested":{"gateway_key":"private","access_token":"secret","state":"connected"}}
    out=bridge.scrub(raw)
    assert out["device"]=="SM-S948B"
    assert out["token"]=="[REDACTED]"
    assert out["nested"]["gateway_key"]=="[REDACTED]"
    assert out["nested"]["access_token"]=="[REDACTED]"
    assert out["nested"]["state"]=="connected"

def test_unknown_or_mutating_operations_blocked_before_credentials(monkeypatch,capsys):
    monkeypatch.setattr(sys,"argv",["bridge","--tool","control_phone_input"])
    assert bridge.main()==3
    assert "action_requires_explicit_approval" in capsys.readouterr().out
    monkeypatch.setattr(sys,"argv",["bridge","--tool","remote_system"])
    assert bridge.main()==2
    assert "unsupported_control_tool_namespace" in capsys.readouterr().out

def test_client_has_no_automatic_command_retries():
    src=PATH.read_text(encoding="utf-8")
    assert "RETRY=not_automatic" in src
    assert "follow_redirects=False" in src
    assert "trust_env=False" in src
    assert "mcp-gateway-token.txt" in src
