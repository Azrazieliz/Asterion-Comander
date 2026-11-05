from fastapi.testclient import TestClient
from asterion_remote import pairing
from asterion_remote.app import app

def test_private_peers_only():
    for address in ('192.168.1.5','10.20.30.4','127.0.0.1','100.80.3.4'):
        assert pairing.private_peer(address)
    for address in ('8.8.8.8','invalid','255.255.255.255','1.2.3.4'):
        assert not pairing.private_peer(address)

def test_one_time_pin_and_token(tmp_path,monkeypatch):
    monkeypatch.setattr(pairing,'STATE',tmp_path)
    monkeypatch.setattr(pairing,'PAIRED',tmp_path/'clients.json')
    monkeypatch.setattr(pairing,'PIN_FILE',tmp_path/'pin.txt')
    monkeypatch.setattr(pairing,'_pin',None)
    monkeypatch.setattr(pairing,'_attempts',{})
    code=pairing.create_code()
    assert len(code)==8 and code.isnumeric()
    client=TestClient(app,client=('192.168.1.99',44531))
    incorrect='0'*8 if code!='0'*8 else '1'*8
    assert client.post('/api/v1/pair',json={'name':'Android','code':incorrect}).status_code==401
    response=client.post('/api/v1/pair',json={'name':'Android','code':code})
    assert response.status_code==200,response.text
    token=response.json()['token']
    assert len(token)>32 and pairing.is_authorized(token)
    assert client.get('/api/v1/health',headers={'Authorization':'Bearer '+token}).status_code==200
    assert client.post('/api/v1/pair',json={'name':'Other','code':code}).status_code==401
    assert not pairing.PIN_FILE.exists()
    assert 'hash' not in pairing.authorized_devices()[0]
    assert token not in pairing.PAIRED.read_text()

def test_pairing_rate_limit(tmp_path,monkeypatch):
    monkeypatch.setattr(pairing,'STATE',tmp_path)
    monkeypatch.setattr(pairing,'PAIRED',tmp_path/'clients.json')
    monkeypatch.setattr(pairing,'PIN_FILE',tmp_path/'pin.txt')
    monkeypatch.setattr(pairing,'_attempts',{})
    code=pairing.create_code()
    client=TestClient(app,client=('10.0.0.9',9921))
    wrong='9'*8 if code!='9'*8 else '8'*8
    for n in range(6):
        assert client.post('/api/v1/pair',json={'name':'Bad','code':wrong}).status_code==401
    assert client.post('/api/v1/pair',json={'name':'Bad','code':code}).status_code==429
