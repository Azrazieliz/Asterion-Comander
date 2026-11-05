"""Native-phone MCP contract must not expose ADB as the primary control path."""
from asterion_remote import mcp_protocol

def test_native_android_tools_are_available():
    names={tool["name"] for tool in mcp_protocol.TOOLS}
    assert {"control_phone_status","control_phone_health","control_phone_screen","control_phone_ui","control_phone_input","control_script_run","control_script_parallel"}.issubset(names)
    assert not any(n.startswith("remote_android_") for n in names)

def test_native_android_status_uses_native_bridge(monkeypatch):
    from asterion_remote import native_routes
    monkeypatch.setattr(native_routes,"phone_status",lambda:{"paired":True,"reachable":True,"device":"Android"})
    result=mcp_protocol.handle_rpc({"jsonrpc":"2.0","id":101,"method":"tools/call","params":{"name":"control_phone_status","arguments":{}}})
    assert result["result"]["content"][0]["type"]=="text"
    assert '"reachable": true' in result["result"]["content"][0]["text"]

def test_native_input_dispatch_does_not_call_adb(monkeypatch):
    from asterion_remote import native_routes
    called=[]
    monkeypatch.setattr(native_routes,"phone_input",lambda arg:called.append(arg) or {"ok":True})
    out=mcp_protocol.invoke_tool("control_phone_input",{"action":"home"})
    assert out=={"ok":True} and called[0].action=="home"
