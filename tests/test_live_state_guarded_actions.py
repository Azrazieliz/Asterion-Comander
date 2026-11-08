"""The default direct interface observes fresh Android UI before each action.

No phone, screenshot, credential, or developer machine access is needed.
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from asterion_remote import live_stream


class MockResponse:
    def __init__(self,value):
        self.value=value
    def raise_for_status(self):
        pass
    def json(self):
        return self.value


class Android:
    def __init__(self):
        self.package="com.android.settings"
        self.calls=[]
        self.label="Settings"
    def get(self,url,headers):
        assert url.endswith("/ui")
        assert headers["Authorization"]=="Bearer simulated-phone-token"
        return MockResponse({
            "available":True,
            "foreground_package":self.package,
            "keyboard":{"active":False,"editor_package":""},
            "root":{"class":"android.widget.FrameLayout",
                    "text":self.label,"description":"",
                    "bounds":[0,0,1080,2340],"children":[]},
        })
    def post(self,url,headers,json):
        self.calls.append((url.split("/")[-1],json))
        if url.endswith("/input"):
            return MockResponse({"ok":True})
        if url.endswith("/apps/launch"):
            return MockResponse({"intent_dispatched":
                                 self.package=="com.asterion.control"})
        assert False, "unexpected endpoint"
    def close(self):
        pass


def receive_json(session, typ):
    for _ in range(4):
        message=session.receive_json()
        if message.get("type")==typ:
            return message
    raise AssertionError("Missing direct response: "+typ)


def setup(monkeypatch):
    device=Android()
    monkeypatch.setenv("ASTERION_API_TOKEN","S"*48)
    monkeypatch.setattr(live_stream,"load_phone_pairing",
                        lambda: {"base_url":"http://192.168.1.88:8973",
                                 "token":"simulated-phone-token"})
    monkeypatch.setattr(live_stream.httpx,"Client",lambda **kwargs:device)
    app=FastAPI()
    live_stream.install_stream(app,lambda _:b"unused",lambda _:{"ok":True})
    return app,device


def test_live_inspect_and_state_guarded_action(monkeypatch):
    app,device=setup(monkeypatch)
    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/stream/phone") as ws:
            ws.send_json({"token":"S"*48,"video":False})
            ws.send_json({"type":"inspect","id":"state-1"})
            state=receive_json(ws,"ui_state")
            assert state["ok"] is True
            assert state["state"]["foreground_package"]=="com.android.settings"
            assert len(state["state_id"])>16
            ws.send_json({"type":"input","id":"tap-1",
                          "state_id":state["state_id"],
                          "expect_package":"com.android.settings",
                          "payload":{"action":"tap","x":90,"y":130}})
            ack=receive_json(ws,"input_ack")
            assert ack["ok"] is True
            assert len(device.calls)==1
            assert device.calls[0][0]=="input"
            # The same request ID must not execute a second input.
            ws.send_json({"type":"input","id":"tap-1",
                          "payload":{"action":"tap","x":90,"y":130}})
            assert receive_json(ws,"input_ack")["ok"] is False
            assert len(device.calls)==1


def test_changed_screen_rejected_without_tap(monkeypatch):
    app,device=setup(monkeypatch)
    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/stream/phone") as ws:
            ws.send_json({"token":"S"*48,"video":False})
            ws.send_json({"type":"inspect","id":"inspect-1"})
            state=receive_json(ws,"ui_state")
            device.label="Security settings"
            ws.send_json({"type":"input","id":"tap-2",
                          "state_id":state["state_id"],
                          "payload":{"action":"tap","x":90,"y":130}})
            response=receive_json(ws,"input_ack")
            assert response["ok"] is False
            assert "changed" in response["error"]
            assert device.calls==[]


def test_wrong_foreground_app_rejected(monkeypatch):
    app,device=setup(monkeypatch)
    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/stream/phone") as ws:
            ws.send_json({"token":"S"*48,"video":False})
            ws.send_json({"type":"input","id":"tap-3",
                          "expect_package":"com.openai.chatgpt",
                          "payload":{"action":"tap","x":90,"y":130}})
            response=receive_json(ws,"input_ack")
            assert response["ok"] is False
            assert "Wrong foreground" in response["error"]
            assert device.calls==[]


def test_live_approved_app_launch_requires_existing_control_foreground(monkeypatch):
    app,device=setup(monkeypatch)
    device.package="com.asterion.control"
    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/stream/phone") as ws:
            ws.send_json({"token":"S"*48,"video":False})
            ws.send_json({"type":"inspect","id":"inspect-control"})
            state=receive_json(ws,"ui_state")
            ws.send_json({"type":"launch_app","id":"launch-1",
                          "state_id":state["state_id"],
                          "expect_package":"com.asterion.control",
                          "package":"com.sec.android.app.clockpackage"})
            reply=receive_json(ws,"launch_ack")
            assert reply["ok"] is True
            assert reply["intent_dispatched"] is True
            assert reply["verified_foreground"] is False
            assert device.calls[-1][0]=="launch"


def test_semantic_inspection_does_not_require_video_stream(monkeypatch):
    app,device=setup(monkeypatch)
    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/stream/phone") as ws:
            ws.send_json({"token":"S"*48,"video":False})
            for i in range(3):
                ws.send_json({"type":"inspect","id":"read-"+str(i)})
                result=receive_json(ws,"ui_state")
                assert result["ok"] and result["state"]["available"]
            assert device.calls==[]
