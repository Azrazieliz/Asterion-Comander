"""Native R03/R04 signed capability and direct intent safety contracts.

Android package must compile separately; this covers the Windows original
WSS RPC allowlist and prevents a duplicate download/generation engine.
"""
from pathlib import Path
import pytest
from fastapi import HTTPException

from asterion_remote.native_phone_rpc import resolved_tool

ROOT=Path(__file__).resolve().parents[1]
ANDROID=ROOT/"android/app/src/main/java/com/asterion/control"
BRIDGE=(ANDROID/"AppBridge.java").read_text("utf8")
FAST=(ANDROID/"AppIntentFastPath.java").read_text("utf8")
MCP=(ANDROID/"AndroidMcp.java").read_text("utf8")
PHONE=(ROOT/"asterion_remote/phone_bridge.py").read_text("utf8")
ROUTES=(ROOT/"asterion_remote/native_routes.py").read_text("utf8")


def test_read_only_signed_provider_capability_tool_is_explicit():
    tool,args=resolved_tool("POST","/app-bridge/capabilities",
                            {"package":"com.azrael.pixivdumpsync.acceptance"})
    assert tool=="control_phone_app_capabilities"
    assert args["package"]=="com.azrael.pixivdumpsync.acceptance"
    assert "control_phone_app_capabilities" in MCP
    assert "static JSONObject capabilities" in BRIDGE
    assert "asterion.v1.capabilities" in BRIDGE
    assert 'expected.equals(signer(ctx,pkg))' in BRIDGE
    assert "owner_approved" in BRIDGE


def test_native_intent_invoke_is_explicit_and_nonarbitrary():
    payload={"intent":"image","request_id":"owner-creative-0001",
             "payload":{"prompt":"A photo of an apple"}}
    tool,args=resolved_tool("POST","/intent/dispatch",payload)
    assert tool=="control_phone_intent_dispatch"
    assert args==payload
    assert "AppIntentFastPath.route(owner,args)" in MCP
    assert "AppBridge.invoke(owner,invocation)" in FAST
    assert "AppBridge.capabilities(owner,pkg)" in FAST
    assert "ambiguous_signed_capabilities" in FAST
    assert "no_approved_signed_specialist_capability" in FAST
    assert "duplicate" in BRIDGE


@pytest.mark.parametrize("method,path",[
    ("GET","/app-bridge/capabilities"),
    ("GET","/intent/dispatch"),
    ("POST","/tools/call"),
    ("POST","/file/write"),
    ("POST","/download"),
    ("POST","/model/infer"),
])
def test_no_generic_tool_or_duplicated_engine_route(method,path):
    with pytest.raises(HTTPException) as err:
        resolved_tool(method,path,{})
    assert err.value.status_code==404


def test_control_only_uses_original_authenticated_phone_bridge():
    for p in ("'/app-bridge/capabilities'","'/intent/dispatch'"):
        assert p in PHONE
    assert "request('/app-bridge/capabilities','POST'" in ROUTES
    assert "request('/intent/dispatch','POST'" in ROUTES
    assert "DownloadManager" not in FAST
    assert "OnDeviceLlm" not in FAST
    assert "httpx.Client" not in FAST
    assert "owner_approved" in FAST
