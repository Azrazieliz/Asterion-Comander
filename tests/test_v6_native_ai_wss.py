"""M4: native model jobs reuse signed phone WSS and fail closed.

These are real Windows backend regression tests, not Android inference tests;
actual GGUF+JNI+installed Samsung inference is required separately.
"""
from pathlib import Path
import httpx
import pytest
from fastapi import HTTPException

from asterion_remote import phone_bridge
from asterion_remote.native_phone_rpc import resolved_tool

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"android/app/src/main/java/com/asterion/control"
JOB=(SRC/"OnDeviceAiJobs.java").read_text("utf8")
MCP=(SRC/"AndroidMcp.java").read_text("utf8")
ROUTE=(ROOT/"asterion_remote/native_routes.py").read_text("utf8")


@pytest.mark.parametrize("method,path,name",[
    ("GET","/ai/model/status","control_phone_ai_model_status"),
    ("POST","/ai/jobs/submit","control_phone_ai_submit"),
    ("POST","/ai/jobs/status","control_phone_ai_job"),
    ("POST","/ai/jobs/cancel","control_phone_ai_cancel"),
])
def test_native_ai_only_explicitly_typed_wss_tools(method,path,name):
    payload={} if method=="GET" else {"request_id":"native-model-job-0001"}
    tool,data=resolved_tool(method,path,payload)
    assert tool==name
    assert data==payload
    assert name in MCP


def test_native_only_model_does_not_leak_to_private_lan(monkeypatch):
    events=[]
    monkeypatch.setattr(phone_bridge,"load",
                        lambda:{"token":"z"*40,"base_url":"http://192.168.1.20:8973"})
    def no_session(*args,**kwargs):
        events.append((args[0],args[1]))
        return None
    monkeypatch.setattr(phone_bridge,"_request_via_outbound_wss",no_session)
    class BlockLan:
        def request(self,*args,**kwargs):
            pytest.fail("Native model operation bypassed WSS")
    monkeypatch.setattr(phone_bridge,"_phone_http",BlockLan())
    with pytest.raises(HTTPException) as err:
        phone_bridge.request_native_only("/ai/jobs/submit","POST",
                        {"request_id":"native-model-job-0001","prompt":"Hello"})
    assert err.value.status_code==503
    assert events==[("/ai/jobs/submit","POST")]


def test_native_inference_result_wss_and_no_duplicate_dispatch(monkeypatch):
    events=[]
    monkeypatch.setattr(phone_bridge,"load",
                        lambda:{"token":"z"*40,"base_url":"http://192.168.1.20:8973"})
    def native(path,method,payload,timeout,token):
        events.append((path,method,payload["request_id"]))
        return httpx.Response(200,json={"request_id":payload["request_id"],
                                        "state":"queued","reused":False})
    monkeypatch.setattr(phone_bridge,"_request_via_outbound_wss",native)
    result=phone_bridge.request_native_only("/ai/jobs/submit","POST",
                  {"request_id":"native-job-1111","prompt":"Explain this"}).json()
    assert result["state"]=="queued"
    assert len(events)==1


@pytest.mark.parametrize("path,method",[
    ("/any/command","POST"),
    ("/ai/jobs/submit","GET"),
    ("/ai/model/status","POST"),
    ("/apps/launch","POST"),
])
def test_model_wrapper_rejects_arbitrary_tools(path,method):
    with pytest.raises(HTTPException) as error:
        phone_bridge.request_native_only(path,method)
    assert error.value.status_code in (404,405)


def test_model_jobs_have_real_offline_execution_and_private_journal():
    assert "OnDeviceLlm.generate(ctx,prompt,job.request)" in JOB
    assert "OnDeviceLlm.cancel(job.request)" in JOB
    assert "Executors.newSingleThreadExecutor" in JOB
    assert "SharedPreferences" in JOB
    assert "prompt_sha256" in JOB
    assert "previous_process_outcome_unavailable" in JOB
    assert "retry_safe" in JOB
    assert 'putString(job.id,receipt.toString())' in JOB
    assert 'put("prompt",prompt)' not in JOB
    assert "newSingleThreadExecutor" in JOB
    assert "request_native_only('/ai/jobs/submit'" in ROUTE
    assert "request_native_only('/ai/jobs/status'" in ROUTE
    assert "request_native_only('/ai/jobs/cancel'" in ROUTE
