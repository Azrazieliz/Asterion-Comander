"""Owner-only authenticated phone operations must bypass stale Windows proxy routes."""
import pytest
from asterion_remote import github_bridge, phone_bridge


def test_voice_and_cycle_commands_call_existing_phone_token(monkeypatch):
    calls=[]
    import importlib
    class Reply:
        def json(self): return {"ok":True}
    def capture(path,method,payload,timeout):
        calls.append((path,method,payload,timeout));return Reply()
    monkeypatch.setattr(importlib.import_module("asterion_remote.phone_bridge"),"request",capture)
    for op,params,path in [
        ('phone_voice_status',{},'/voice/status'),
        ('phone_voice_ack',{'question_id':'voice-example-001'},'/voice/ack'),
        ('phone_cycle_status',{},'/cycles/status'),
        ('phone_cycle_queue',{'project':'NoWorld','checkpoint_id':'checkpoint-001'},'/continuation/queue'),
        ('phone_cycle_dispatch',{},'/continuation/dispatch'),
        ('phone_cycle_cancel',{},'/continuation/cancel'),
        ('phone_performance_status',{},'/performance/status')]:
        assert github_bridge.run({'op':op,'params':params},'windows-token')=={'ok':True}
        actual,method,body,timeout=calls[-1]
        assert actual==path and timeout==10.0
        assert body==(params if method=="POST" else None)



def test_owner_native_api_rejects_unsafe_arguments(monkeypatch):
    monkeypatch.setattr(github_bridge,'phone_native',lambda *a:pytest.fail('Bad input reached phone'))
    for op,args in [
        ('phone_voice_question',{'text':''}),
        ('phone_voice_question',{'text':'a'*701}),
        ('phone_performance_mode',{'mode':'overclock'}),
        ('phone_voice_status',{'unexpected':'data'})]:
        with pytest.raises(ValueError):
            github_bridge.run({'op':op,'params':args},'existing-token')
