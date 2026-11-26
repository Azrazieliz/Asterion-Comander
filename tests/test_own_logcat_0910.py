"""Asterion private Android logcat and no-ADB diagnostics contract."""
from pathlib import Path
from asterion_remote import github_bridge, phone_bridge, native_routes
ROOT=Path(__file__).resolve().parents[1]

def test_logcat_only_reads_owner_app_pid_and_redacts_tokens():
    agent=(ROOT/"android/app/src/main/java/com/asterion/control/AgentService.java").read_text()
    assert 'path.equals("/diagnostics/logcat")' in agent
    assert '"--pid="+pid' in agent
    assert "android.os.Process.myPid()" in agent
    assert 'readNBytes(12288)' in agent
    assert 'Bearer [REDACTED]' in agent
    assert 'process.waitFor(2' in agent

def test_authenticated_diagnostics_routes_use_existing_pairing(monkeypatch):
    assert github_bridge.PHONE_NATIVE["phone_logcat"] == ("GET","/diagnostics/logcat")
    assert callable(native_routes.phone_own_logcat)
    import importlib
    seen=[]
    class Reply:
        def json(self): return {"ok":True,"scope":"own_app_pid_only"}
    def capture(path,method,payload,timeout):
        seen.append((path,method,payload,timeout));return Reply()
    monkeypatch.setattr(importlib.import_module("asterion_remote.phone_bridge"),"request",capture)
    result=github_bridge.run({"op":"phone_logcat","params":{}}, "existing-pc-token")
    assert result=={"ok":True,"scope":"own_app_pid_only"}
    assert seen==[("/diagnostics/logcat","GET",None,10.0)]
