"""Original bridge routes use WSS-first native RPC, with explicit typed partner inputs."""
import pytest
from asterion_remote import github_bridge as bridge, phone_bridge


class Reply:
    def json(self):
        return {"ok": True, "status": "observed"}


def test_native_voice_and_network_share_original_wss_first_transport(monkeypatch):
    calls=[]
    def request(path,method,payload,timeout):
        calls.append((path,method,payload,timeout))
        return Reply()
    import importlib
    monkeypatch.setattr(importlib.import_module("asterion_remote.phone_bridge"),"request",request)
    for op in ("phone_voice_status","phone_network_status"):
        assert bridge.run({"op":op,"params":{}}, "redacted")["ok"]
    assert calls == [("/voice/status","GET",None,10.0),
                     ("/network/status","GET",None,10.0)]


def test_signed_partner_discovery_and_lifecycle_use_existing_routes(monkeypatch):
    calls=[]
    monkeypatch.setattr(bridge,"phone_native",
        lambda path,method,body: calls.append((path,method,body)) or {"ok":True})
    pkg="com.azrael.pixivdumpsync.acceptance"
    ident="browser-12345678-1234-1234-1234-123456789abc"
    operations=[
        ("phone_app_bridges",{},"/app-bridge/apps","GET",None),
        ("phone_app_capabilities",{"package":pkg},"/app-bridge/capabilities","POST",{"package":pkg}),
        ("phone_app_invoke",{"package":pkg,"action":"download.queue","request_id":ident,
                            "payload":{"url":"https://example.com/file"}},"/app-bridge/invoke","POST",None),
        ("phone_app_operation",{"package":pkg,"request_id":ident,"cancel":False},"/app-bridge/operation","POST",None),
        ("phone_app_operation",{"package":pkg,"request_id":ident,"cancel":True},"/app-bridge/operation","POST",None),
    ]
    for op,args,path,method,body in operations:
        assert bridge.run({"op":op,"params":args}, "redacted")["ok"]
        assert calls[-1]==(path,method,args if method=="POST" else body)


@pytest.mark.parametrize("op,args",[
    ("phone_app_bridges",{"package":"com.example.app"}),
    ("phone_app_capabilities",{"package":"com.example.app/../"}),
    ("phone_app_capabilities",{"package":"com.example.app","approve":True}),
    ("phone_app_invoke",{"package":"com.example.app","request_id":"bad","action":"download"}),
    ("phone_app_invoke",{"package":"com.example.app","request_id":"long-enough-id","action":"../../shell"}),
    ("phone_app_invoke",{"package":"com.example.app","request_id":"long-enough-id","action":"download","payload":{"data":"x"*4097}}),
    ("phone_app_operation",{"package":"com.example.app","request_id":"long-enough-id","cancel":"true"}),
])
def test_bad_partner_arguments_never_dispatch(monkeypatch,op,args):
    monkeypatch.setattr(bridge,"phone_native",lambda *a:pytest.fail("Invalid operation dispatched"))
    with pytest.raises(ValueError):
        bridge.run({"op":op,"params":args},"redacted")
