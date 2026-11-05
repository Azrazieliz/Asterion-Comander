import os
from pathlib import Path

os.environ['ASTERION_API_TOKEN'] = 'test-asterion-token-abcdefghijklmnopqrstuvwxyz'
os.environ['ASTERION_REMOTE_ROOT'] = str(Path(__file__).resolve().parents[1])

from fastapi.testclient import TestClient
from asterion_remote.app import app, ROOT
from asterion_remote import app as remote

AUTH={'Authorization': f'Bearer {os.environ["ASTERION_API_TOKEN"]}'}
MCP={**AUTH,'Accept':'application/json, text/event-stream'}


def test_auth_security():
    with TestClient(app) as c:
        assert c.get('/api/v1/health').status_code == 401
        assert c.get('/api/v1/files', headers={'Authorization':'Bearer wrong'}).status_code == 401
        assert c.post('/mcp',headers={'Accept':'application/json, text/event-stream'},json={}).status_code == 401
        assert c.get('/api/v1/health',headers=AUTH).json()['app']=='Asterion Control'


def test_static_ui():
    with TestClient(app) as c:
        assert 'Asterion Control' in c.get('/').text
        assert c.get('/static/app.js').status_code==200
        assert c.get('/static/style.css').status_code==200
        assert c.get('/manifest.webmanifest').json()['display']=='standalone'


def test_files_crud_and_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(remote,'ROOT',tmp_path)
    with TestClient(app) as c:
        assert c.get('/api/v1/files',headers=AUTH,params={'path':'../'}).status_code==403
        assert c.post('/api/v1/files/mkdir',headers=AUTH,json={'path':'notes'}).status_code==200
        assert c.put('/api/v1/files/write',headers=AUTH,json={'path':'notes/a.txt','content':'hello'}).status_code==200
        assert c.get('/api/v1/files/read',headers=AUTH,params={'path':'notes/a.txt'}).json()['content']=='hello'
        assert c.put('/api/v1/files/write',headers=AUTH,json={'path':'notes/a.txt','content':'bye'}).status_code==409
        assert c.put('/api/v1/files/write',headers=AUTH,json={'path':'notes/a.txt','content':'bye','overwrite':True}).status_code==200
        assert c.get('/api/v1/files/search',headers=AUTH,params={'q':'a.txt'}).json()['items'][0]['path']=='notes/a.txt'
        assert c.get('/api/v1/files/download',headers=AUTH,params={'path':'notes/a.txt'}).content==b'bye'
        assert c.post('/api/v1/files/move',headers=AUTH,json={'source':'notes/a.txt','destination':'notes/b.txt'}).status_code==200
        assert c.delete('/api/v1/files',headers=AUTH,params={'path':'notes/b.txt'}).status_code==200
        assert c.delete('/api/v1/files',headers=AUTH,params={'path':'.'}).status_code==403
        outside=tmp_path/'jump'
        outside.symlink_to(Path('/tmp'),target_is_directory=True)
        assert c.get('/api/v1/files',headers=AUTH,params={'path':'jump'}).status_code==403
    monkeypatch.setattr(remote,'ROOT',ROOT)


def test_upload_and_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(remote,'ROOT',tmp_path)
    with TestClient(app) as c:
        resp=c.put('/api/v1/files/upload?path=bytes.dat',headers=AUTH,content=b'\x00hello')
        assert resp.status_code==200
        assert (tmp_path/'bytes.dat').read_bytes()==b'\x00hello'
        assert c.put('/api/v1/files/upload?path=bytes.dat',headers=AUTH,content=b'1').status_code==409
        assert c.put('/api/v1/files/upload?path=bytes.dat&overwrite=true',headers=AUTH,content=b'2').status_code==200
        assert (tmp_path/'bytes.dat').read_bytes()==b'2'
    monkeypatch.setattr(remote,'ROOT',ROOT)


def test_system_processes():
    with TestClient(app) as c:
        assert 'memory' in c.get('/api/v1/system',headers=AUTH).json()
        assert isinstance(c.get('/api/v1/processes',headers=AUTH).json()['items'],list)
        assert c.post(f'/api/v1/processes/{os.getpid()}/terminate',headers=AUTH).status_code==403
        assert c.post('/api/v1/commands',headers=AUTH,json={'command':'echo testing'}).status_code==403


def test_mcp_protocol_and_security():
    with TestClient(app) as c:
        init=c.post('/mcp',headers=MCP,json={'jsonrpc':'2.0','id':1,'method':'initialize','params':{}})
        assert init.status_code==200
        assert init.json()['result']['capabilities']['tools']=={'listChanged':False}
        catalog=c.post('/mcp',headers=MCP,json={'jsonrpc':'2.0','id':2,'method':'tools/list'}).json()
        assert len(catalog['result']['tools'])>=16
        call=c.post('/mcp',headers=MCP,json={'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'remote_health','arguments':{}}})
        assert 'asterion' in call.json()['result']['content'][0]['text'].lower()
        denied=c.post('/mcp',headers={**MCP,'Origin':'https://evil.example'},json={'jsonrpc':'2.0','id':1,'method':'tools/list'})
        assert denied.status_code==403
        assert c.post('/mcp',headers=AUTH,json={'jsonrpc':'2.0','id':1,'method':'tools/list'}).status_code==406
        note=c.post('/mcp',headers=MCP,json={'jsonrpc':'2.0','method':'notifications/initialized'})
        assert note.status_code==202
        wrong=c.post('/mcp',headers=MCP,json={'jsonrpc':'2.0','id':5,'method':'tools/call','params':{'name':'remote_pwn','arguments':{}}})
        assert wrong.json()['result']['isError']


def test_adb_devices_and_input_safe(monkeypatch):
    calls=[]
    def fake_run(args, timeout=20, raw=False):
        calls.append(args)
        if args[-2:]==['devices','-l']:
            return 'List of devices attached\nABC123 device product:demo model:One\nBAD unauthorized\n'
        if args[-3:]==['exec-out','screencap','-p']:
            return b'\x89PNG\r\n\x1a\nxyz'
        return ''
    monkeypatch.setattr(remote,'run_external',fake_run)
    with TestClient(app) as c:
        d=c.get('/api/v1/android/devices',headers=AUTH)
        assert d.json()['items'][0]['serial']=='ABC123'
        assert c.get('/api/v1/android/%2Dfoo/screen',headers=AUTH).status_code==422
        assert c.get('/api/v1/android/ABC123/screen',headers=AUTH).content.startswith(b'\x89PNG')
        assert c.post('/api/v1/android/ABC123/input',headers=AUTH,json={'action':'tap','x':10,'y':20}).status_code==200
        assert c.post('/api/v1/android/ABC123/input',headers=AUTH,json={'action':'text','text':'hi world'}).status_code==200
        assert c.post('/api/v1/android/ABC123/shell',headers=AUTH,json={'command':'ls'}).status_code==403
        assert any('input text' in ' '.join(args) for args in calls)
        assert c.post('/api/v1/android/ABC123/input',headers=AUTH,json={'action':'text','text':'♥'}).status_code==422


def test_actual_shell_job_lifecycle(tmp_path, monkeypatch):
    import time
    import sys
    monkeypatch.setattr(remote,'ROOT',tmp_path)
    monkeypatch.setattr(remote,'RUNTIME',tmp_path/'.runtime')
    monkeypatch.setattr(remote,'ALLOW_SHELL',True)
    with TestClient(app) as c:
        cmd=f'"{sys.executable}" -c "print(913579)"'
        r=c.post('/api/v1/commands',headers=AUTH,json={'command':cmd,'cwd':'.'})
        assert r.status_code==200,r.text
        job=r.json()['id']
        for _ in range(40):
            record=c.get('/api/v1/commands/'+job,headers=AUTH).json()
            if record['status']=='finished': break
            time.sleep(.05)
        assert record['exit_code']==0
        assert '913579' in record['output']
        assert c.get('/api/v1/commands',headers=AUTH).status_code==200
    monkeypatch.setattr(remote,'ALLOW_SHELL',False)
    monkeypatch.setattr(remote,'ROOT',ROOT)


def test_monitors_and_desktop_input_mock(monkeypatch):
    import sys
    import types
    from PIL import Image
    class FakeGrab:
        def __init__(self):
            self.size=(8,6)
            self.rgb=Image.new('RGB',self.size,color='blue').tobytes()
    class FakeMss:
        monitors=[{'left':-100,'top':0,'width':200,'height':100},
                  {'left':20,'top':50,'width':8,'height':6}]
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def grab(self,rect):return FakeGrab()
    actions=[]
    fake_pg=types.SimpleNamespace(FAILSAFE=False,click=lambda x,y,**kw: actions.append((x,y,kw)))
    monkeypatch.setitem(sys.modules,'mss',types.SimpleNamespace(mss=FakeMss))
    monkeypatch.setitem(sys.modules,'pyautogui',fake_pg)
    with TestClient(app) as c:
        monitors=c.get('/api/v1/monitors',headers=AUTH).json()
        assert monitors['items'][1]['left']==20
        screen=c.get('/api/v1/screen?monitor=1',headers=AUTH)
        assert screen.status_code==200 and screen.headers['content-type']=='image/jpeg'
        r=c.post('/api/v1/input',headers=AUTH,json={'action':'click','x':2,'y':3,'monitor':1})
        assert r.status_code==200
        assert actions==[(22,53,{})]
        assert c.get('/api/v1/screen?monitor=8',headers=AUTH).status_code==422


def test_wifi_pairing_validation(monkeypatch):
    seen=[]
    def fake_adb(serial,*args,timeout=20,raw=False):
        seen.append((serial,args))
        return 'connected'
    monkeypatch.setattr(remote,'adb',fake_adb)
    with TestClient(app) as c:
        good=c.post('/api/v1/android/connect',headers=AUTH,json={'address':'192.168.1.25:39123'})
        assert good.status_code==200
        bad=c.post('/api/v1/android/connect',headers=AUTH,json={'address':'192.168.1.25;touch /tmp/x'})
        assert bad.status_code==422
        paired=c.post('/api/v1/android/pair',headers=AUTH,json={'address':'192.168.1.25:39123','code':'123456'})
        assert paired.status_code==200
        assert seen[-1][1]==('pair','192.168.1.25:39123','123456')
