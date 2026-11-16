import os
from pathlib import Path
from fastapi.testclient import TestClient
from asterion_remote.app import app
from asterion_remote import control_services as service

AUTH = {'Authorization': 'Bearer '+os.environ.get('ASTERION_API_TOKEN','z'*40)}


def test_private_scripts_api_and_health():
    with TestClient(app) as c:
        assert c.get('/api/v1/internal/scripts').status_code == 401
        assert c.get('/api/v1/device-health').status_code == 401
        assert c.get('/api/v1/internal/scripts', headers=AUTH).status_code == 200
        response = c.get('/api/v1/device-health', headers=AUTH)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data['disks'], list)
        assert 'thermals' in data and 'available' in data['thermals']
        assert 'battery' in data
        assert 'cpu_percent' in data


def test_script_ids_and_argument_validation(tmp_path, monkeypatch):
    monkeypatch.setattr(service, 'SCRIPT_ROOT', tmp_path)
    p = tmp_path / 'demo.py'
    p.write_text('print(42)')
    assert service.safe_script('demo') == p
    assert 'demo' in [x['id'] for x in service.script_list()]
    assert service.script_command('demo', ['a b'])[2] == 'a b'
    for invalid in ['../demo', 'demo/x', '-demo']:
        try:
            service.safe_script(invalid)
        except Exception:
            pass
        else:
            raise AssertionError('Unsafe script id accepted')
    try:
        service.script_command('demo', ['bad\x00value'])
    except Exception:
        pass
    else:
        raise AssertionError('Null byte accepted')


def test_hidden_terminal_not_navigation():
    with TestClient(app) as c:
        html = c.get('/').text
        assert 'data-page="terminal"' not in html
        assert 'Asterion Control' in html


def test_parallel_saved_scripts_execute_and_report(tmp_path, monkeypatch):
    from asterion_remote import app as mod
    monkeypatch.setattr(service, 'SCRIPT_ROOT', tmp_path)
    monkeypatch.setattr(mod, 'RUNTIME', tmp_path / 'runtime')
    monkeypatch.setattr(mod, 'ALLOW_SHELL', True)
    (tmp_path / 'alpha.py').write_text('print("alpha-done")')
    (tmp_path / 'beta.py').write_text('print("beta-done")')
    with TestClient(app) as c:
        res=c.post('/api/v1/internal/scripts/batch', headers=AUTH,
            json={'mode':'parallel','jobs':[{'script_id':'alpha'}, {'script_id':'beta'}]})
        assert res.status_code == 200, res.text
        jobs=res.json()['jobs']
        assert len(jobs) == 2 and jobs[0]['id'] != jobs[1]['id']
        for job in jobs:
            import time
            for _ in range(100):
                r=c.get('/api/v1/commands/'+job['id'], headers=AUTH)
                if r.json()['exit_code'] is not None:
                    break
                time.sleep(.02)
            assert r.json()['exit_code']==0
            assert '-done' in r.json()['output']


def test_command_stop_rejects_failed_windows_taskkill(monkeypatch):
    """Regression: a failed Windows taskkill must never return ok=true."""
    from types import SimpleNamespace
    from fastapi import HTTPException
    from asterion_remote import app as api

    class RunningProcess:
        pid = 31415
        def poll(self):
            return None

    def failed_taskkill(*args, **kwargs):
        assert args[0][:2] == ['taskkill', '/PID']
        return SimpleNamespace(returncode=5)

    monkeypatch.setattr(api, 'COMMANDS', {'test-job': {'proc': RunningProcess()}})
    monkeypatch.setattr(api, 'os', SimpleNamespace(name='nt'))
    monkeypatch.setattr(api, 'subprocess', SimpleNamespace(
        run=failed_taskkill, CREATE_NO_WINDOW=0,
        TimeoutExpired=__import__('subprocess').TimeoutExpired))

    try:
        api.stop_command('test-job')
    except HTTPException as exc:
        assert exc.status_code == 409
        assert 'not terminated' in exc.detail
    else:
        raise AssertionError('False success: taskkill failed while process was live')


def test_command_stop_acknowledges_only_finished_process(monkeypatch):
    """Regression: successful taskkill must be followed by a completed process."""
    from types import SimpleNamespace
    from asterion_remote import app as api

    class Process:
        pid = 31416
        finished = False
        def poll(self):
            return 1 if self.finished else None
        def wait(self, timeout=None):
            assert timeout == 2
            self.finished = True
            return 1

    proc = Process()
    monkeypatch.setattr(api, 'COMMANDS', {'test-job': {'proc': proc}})
    monkeypatch.setattr(api, 'os', SimpleNamespace(name='nt'))
    monkeypatch.setattr(api, 'subprocess', SimpleNamespace(
        run=lambda *a, **k: SimpleNamespace(returncode=0),
        CREATE_NO_WINDOW=0, TimeoutExpired=__import__('subprocess').TimeoutExpired))
    assert api.stop_command('test-job') == {'ok': True}
    assert proc.finished is True
