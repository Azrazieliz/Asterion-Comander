import json
from fastapi.testclient import TestClient
from fastapi import HTTPException
from asterion_remote.app import app
from asterion_remote.security import configured_token
from asterion_remote import phone_bridge

AUTH = {'Authorization':'Bearer '+configured_token()}


def test_phone_api_requires_authorization():
    with TestClient(app) as c:
        for endpoint in ('/api/v1/phone','/api/v1/phone/health','/api/v1/phone/screen','/api/v1/phone/ui'):
            assert c.get(endpoint).status_code == 401
        assert c.post('/api/v1/phone/input',json={'action':'home'}).status_code == 401
        assert c.post('/api/v1/phone/register',json={'base_url':'http://192.168.1.2:8973','token':'A'*40}).status_code == 401


def test_phone_registration_rejects_untrusted_hosts():
    for value in ('https://public.example:8973','http://127.0.0.1:8973','http://8.8.8.8:8973',
                  'http://169.254.169.254:8973','http://example.org:8973','http://192.168.1.2:8973/path'):
        try:
            phone_bridge.validate_base(value)
        except HTTPException: pass
        else: raise AssertionError('Accepted untrusted address '+value)
    assert phone_bridge.validate_base('http://192.168.12.5:8973') == 'http://192.168.12.5:8973'
    assert phone_bridge.validate_base('http://100.90.3.7:8973') == 'http://100.90.3.7:8973'


def test_phone_agent_mock_registration_and_proxy(tmp_path,monkeypatch):
    monkeypatch.setattr(phone_bridge,'STATE',tmp_path/'phone.json')
    class FakeResponse:
        status_code=200
        content=b'\xff\xd8\xff'
        def json(self):return {'ok':True,'device':'TestPhone','screen_width':1080}
    class FakeHttp:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def get(self,url,headers):
            assert headers['Authorization']=='Bearer '+'K'*40
            assert url=='http://192.168.1.7:8973/health'
            return FakeResponse()
        def request(self,method,url,json,headers):
            assert url.startswith('http://192.168.1.7:8973/')
            assert headers['Authorization']=='Bearer '+'K'*40
            return FakeResponse()
    monkeypatch.setattr(phone_bridge.httpx,'Client',FakeHttp)
    with TestClient(app) as c:
        reg=c.post('/api/v1/phone/register',headers=AUTH,json={'base_url':'http://192.168.1.7:8973','token':'K'*40})
        assert reg.status_code==200,reg.text
        assert c.get('/api/v1/phone',headers=AUTH).json()['reachable'] is True
        assert c.get('/api/v1/phone/screen',headers=AUTH).content==b'\xff\xd8\xff'
        assert c.get('/api/v1/phone/ui',headers=AUTH).status_code==200
        assert c.post('/api/v1/phone/input',headers=AUTH,json={'action':'tap','x':8,'y':10}).status_code==200
        assert c.post('/api/v1/phone/input',headers=AUTH,json={'action':'shell','text':'rm -rf /'}).status_code==422


def test_websocket_live_requires_token(monkeypatch):
    from asterion_remote import live_stream
    from asterion_remote import app as main
    monkeypatch.setattr(main,'screenshot',lambda monitor,quality: type('Response',(),{'body':b'\xff\xd8LIVE'})())
    with TestClient(app) as c:
        with c.websocket_connect('/api/v1/stream/desktop') as ws:
            ws.send_json({'token':configured_token(),'monitor':1,'fps':5})
            assert ws.receive_bytes().startswith(b'\xff\xd8')
        with c.websocket_connect('/api/v1/stream/desktop') as ws:
            ws.send_json({'token':'wrong'})
            try:ws.receive_bytes()
            except Exception:pass
            else:raise AssertionError('Wrong token accepted')
