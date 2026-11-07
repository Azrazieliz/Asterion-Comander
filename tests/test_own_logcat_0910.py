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
    monkeypatch.setattr(phone_bridge,"load",lambda:{
        "base_url":"http://192.168.1.22:8973","token":"z"*40})
    seen=[]
    def fake_http(url,token,method="GET",body=None,**kwargs):
        seen.append((url,token,method,body,kwargs))
        return {"ok":True,"scope":"own_app_pid_only"}
    monkeypatch.setattr(github_bridge,"http",fake_http)
    assert github_bridge.run({"op":"phone_logcat","params":{}}, "existing-pc-token")["ok"]
    assert seen[0][0]=="http://192.168.1.22:8973/diagnostics/logcat"
    assert seen[0][1]=="z"*40
    assert seen[0][2]=="GET" and seen[0][4]["control"] is True
