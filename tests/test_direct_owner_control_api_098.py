"""Owner-only authenticated phone operations must bypass stale Windows proxy routes."""
import pytest
import httpx
from asterion_remote import github_bridge, phone_bridge


def test_voice_and_cycle_commands_call_existing_phone_token(monkeypatch):
    calls=[]
    monkeypatch.setattr(phone_bridge,'load',lambda:{'base_url':'http://192.168.1.22:8973','token':'x'*36})
    class PairedTransport:
        def post(self,url,json,headers,timeout):
            assert url=='http://127.0.0.1:8995/phone/rpc'
            assert headers['Authorization']=='Bearer '+'x'*36
            return httpx.Response(503,json={'detail':{'state':'no_session','dispatched':False}})
        def request(self,method,url,json,headers,timeout):
            calls.append((url,headers['Authorization'],method,json,timeout))
            return httpx.Response(200,json={'ok':True})
    monkeypatch.setattr(phone_bridge,'_phone_http',PairedTransport())
    for op,params,path in [
        ('phone_voice_status',{},'/voice/status'),
        ('phone_voice_ack',{'question_id':'voice-example-001'},'/voice/ack'),
        ('phone_cycle_status',{},'/cycles/status'),
        ('phone_cycle_queue',{'project':'NoWorld','checkpoint_id':'checkpoint-001'},'/continuation/queue'),
        ('phone_cycle_dispatch',{},'/continuation/dispatch'),
        ('phone_cycle_cancel',{},'/continuation/cancel'),
        ('phone_performance_status',{},'/performance/status')]:
        assert github_bridge.run({'op':op,'params':params},'windows-token')=={'ok':True}
        url,token,method,body,timeout=calls[-1]
        assert url=='http://192.168.1.22:8973'+path
        assert token=='Bearer '+'x'*36 and timeout==10.0
        if method=='POST':assert body==params
        else:assert body is None


def test_owner_native_api_rejects_unsafe_arguments(monkeypatch):
    monkeypatch.setattr(github_bridge,'phone_native',lambda *a:pytest.fail('Bad input reached phone'))
    for op,args in [
        ('phone_voice_question',{'text':''}),
        ('phone_voice_question',{'text':'a'*701}),
        ('phone_performance_mode',{'mode':'overclock'}),
        ('phone_voice_status',{'unexpected':'data'})]:
        with pytest.raises(ValueError):
            github_bridge.run({'op':op,'params':args},'existing-token')
