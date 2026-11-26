"""Control Model Laboratory keeps all architecture tiers and real evidence distinct."""
import os
from unittest.mock import patch
import pytest
from asterion_remote import model_lab

SHA="a"*64
REV="b"*40

@pytest.fixture
def lab(tmp_path):
    with patch.dict(os.environ,{"ASTERION_MODEL_LAB_ROOT":str(tmp_path)}):
        yield

def add(id="control-14b", total=14.0, active=None, arch="dense", size=8_200_000_000):
    return model_lab.register_candidate(id,"control","Qwen/Qwen3-14B-GGUF",REV,
       SHA,arch,total,active,size,"apache-2.0")

def test_model_lab_has_no_4b_ceiling_and_does_not_auto_promote(lab):
    assert add()["performance_qualified"] is False
    assert add()["automatically_promoted"] is False
    assert model_lab.candidate_matrix("control")["count"]==1
    assert model_lab.candidate_matrix("control")["candidates"][0]["phone_qualified"] is False
    assert model_lab.candidate_matrix("control")["candidates"][0]["parameters_total_b"]==14
    assert model_lab.register_candidate("large-moe","control",
        "Qwen/Qwen3-30B-A3B",REV,"e"*64,
        "moe",30.0,3.0,18_000_000_000,"apache-2.0")["registered"]
    assert model_lab.candidate_matrix("control")["count"]==2

def test_candidate_identity_immutable_across_restart(lab):
    add()
    add()
    with pytest.raises(ValueError,match="cannot_be_rewritten"):
        add(total=12.0)
    assert model_lab.candidate_matrix("control")["count"]==1

def test_ram_cache_and_headroom_are_all_accounted_for(lab):
    add()
    def probe(free):
        return model_lab.record_candidate_probe("control-14b","SM-S948B",
          "android_cpu",8192,weight_resident_bytes=8_000_000_000,
          kv_cache_bytes=850_000_000,scratch_bytes=150_000_000,
          process_overhead_bytes=380_000_000,system_headroom_bytes=700_000_000,
          measured_free_bytes=free,peak_pss_bytes=8_500_000_000,
          prefill_tokens_s=8.0,decode_tokens_s=1.8,thermal_state=1,
          elapsed_s=60.0,evidence_sha256=SHA,verified=False)
    result=probe(4_000_000_000)
    assert result["admission_ledger_bytes"]==10_080_000_000
    assert not result["admission_estimate_fits"]
    assert not result["reasoning_quality_verified"]
    assert not result["promoted"]
    assert model_lab.candidate_matrix("control")["candidates"][0]["probes"][0]["verified"]==0

def test_reject_fake_hardware_and_bad_provenance(lab):
    with pytest.raises(ValueError):
        add(arch="proprietary-gpt")
    with pytest.raises(ValueError):
        add(total=14.0,active=16.0,arch="moe")
    with pytest.raises(ValueError):
        add(size=-1)
    add()
    with pytest.raises(ValueError,match="invalid_resource_ledger"):
        model_lab.record_candidate_probe("control-14b","SM-S948B",
          "android_npu",8192,weight_resident_bytes=-1,kv_cache_bytes=0,
          scratch_bytes=0,process_overhead_bytes=0,system_headroom_bytes=0,
          measured_free_bytes=0,peak_pss_bytes=0,prefill_tokens_s=0.0,
          decode_tokens_s=0.0,thermal_state=0,elapsed_s=1.0,
          evidence_sha256=SHA,verified=False)


def test_adapters_link_to_full_weight_candidate_without_rewriting_evidence(lab):
    add()
    def record(training='b'*64):return model_lab.register_adaptation('owner-lora-01','control-14b',
        adapter_sha256=SHA,training_record_sha256=training,
        evaluation_record_sha256='c'*64,weights_changed=True)
    receipt=record();assert receipt['weights_changed_recorded']
    assert not receipt['owner_behavior_certified']
    record()
    with pytest.raises(ValueError,match='cannot_be_rewritten'):record('d'*64)
    with pytest.raises(ValueError,match='not_registered'):
        model_lab.register_adaptation('owner-lora-02','missing-base',adapter_sha256=SHA,
            training_record_sha256='b'*64,evaluation_record_sha256='c'*64,weights_changed=True)
    assert model_lab.candidate_matrix('control')['count']==1
    assert model_lab.candidate_matrix('control')['candidates'][0]['adaptations'][0]['adapter_sha256']==SHA


def test_authenticated_readonly_lab_candidate_lineage(lab,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from asterion_remote.control_v2_routes import router
    monkeypatch.setenv("ASTERION_API_TOKEN","L"*40)
    add()
    model_lab.register_adaptation('owner-lora-readonly','control-14b',adapter_sha256=SHA,
        training_record_sha256='b'*64,evaluation_record_sha256='c'*64,weights_changed=True)
    app=FastAPI();app.include_router(router)
    with TestClient(app) as client:
        assert client.get('/api/v1/v2/models/candidates').status_code==401
        result=client.get('/api/v1/v2/models/candidates?app=control',headers={'Authorization':'Bearer '+'L'*40})
        assert result.status_code==200
        row=result.json()['candidates'][0]
        assert row['adaptations'][0]['adapter_sha256']==SHA
        assert row['phone_qualified'] is False
        assert client.post('/api/v1/v2/models/candidates',headers={'Authorization':'Bearer '+'L'*40},json={}).status_code==405
