"""Native Control real-time transport contract: frames and inputs share one authenticated socket."""
import os

from fastapi import FastAPI
from fastapi.testclient import TestClient
from asterion_remote.live_stream import install_stream


def test_full_duplex_control_websocket(monkeypatch):
    token = 'test-control-authorization-token-' + 'A' * 48
    monkeypatch.setenv('ASTERION_API_TOKEN', token)
    calls = []
    application = FastAPI()
    install_stream(application, lambda monitor: b'\xff\xd8demo\xff\xd9',
                   lambda payload: calls.append(payload) or {'ok':True})
    with TestClient(application) as client:
        with client.websocket_connect('/api/v1/stream/desktop') as session:
            session.send_json({'token':token,'monitor':1,'fps':15})
            first=session.receive()
            assert first['type']=='websocket.send' and first.get('bytes',b'').startswith(b'\xff\xd8')
            session.send_json({'type':'input','id':'move-1',
                'payload':{'action':'move','monitor':1,'x':150,'y':180}})
            ack=None
            for _ in range(12):
                event=session.receive()
                if event.get('text'):
                    import json
                    item=json.loads(event['text'])
                    if item.get('type')=='input_ack':
                        ack=item
                        break
            assert ack is not None and ack['ok'] is True and ack['id']=='move-1'
            assert isinstance(ack['device_ms'],(int,float))
            assert calls==[{'action':'move','monitor':1,'x':150,'y':180}]


def test_websocket_rejects_wrong_token(monkeypatch):
    monkeypatch.setenv('ASTERION_API_TOKEN','A'*48)
    application=FastAPI()
    install_stream(application,lambda monitor:b'sample',lambda payload:{'ok':True})
    with TestClient(application) as client:
        with client.websocket_connect('/api/v1/stream/desktop') as session:
            session.send_json({'token':'invalid','fps':10})
            event=session.receive()
            assert event['type']=='websocket.close'
            assert event['code']==1008
