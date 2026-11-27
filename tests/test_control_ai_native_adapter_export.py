import json
import pytest
from scripts.control_ai_native_adapter_export import admit,verified_file
from scripts.control_ai_adaptation import file_hash

def fixture(tmp_path):
    base=tmp_path/"base";base.mkdir()
    (base/"config.json").write_text("{}")
    (base/"tokenizer.json").write_text("{}")
    candidate=tmp_path/"candidate";(candidate/"adapter").mkdir(parents=True)
    (candidate/"adapter/adapter_model.safetensors").write_bytes(b"synthetic test fixture, not a model")
    (candidate/"adapter/adapter_config.json").write_text(json.dumps({"peft_type":"LORA","bias":"none"}))
    record={"weights_changed":True,"adapter_only":True,"trainable_sha256_before":"a"*64,
        "trainable_sha256_after":"b"*64,"base_revision_declared":"a"*40,
        "base_files_sha256":{p.name:file_hash(p) for p in base.iterdir()},
        "artifact_sha256":{str(p.relative_to(candidate)):file_hash(p) for p in (candidate/"adapter").iterdir()}}
    (candidate/"candidate.json").write_text(json.dumps(record))
    return candidate,base

def test_conversion_admission_binds_training_and_exact_configuration(tmp_path):
    candidate,base=fixture(tmp_path)
    assert admit(candidate,base)["training_base_config_sha256"]==file_hash(base/"config.json")
    (base/"config.json").write_text('{"different":true}')
    with pytest.raises(ValueError,match="artifact_digest_mismatch"):
        admit(candidate,base)

def test_conversion_admission_rejects_modified_adapter(tmp_path):
    candidate,base=fixture(tmp_path)
    (candidate/"adapter/adapter_model.safetensors").write_bytes(b"changed")
    with pytest.raises(ValueError,match="artifact_digest_mismatch"):
        admit(candidate,base)

def test_conversion_admission_requires_actual_weight_change(tmp_path):
    candidate,base=fixture(tmp_path)
    p=candidate/"candidate.json";record=json.loads(p.read_text());record["trainable_sha256_after"]=record["trainable_sha256_before"];p.write_text(json.dumps(record))
    with pytest.raises(ValueError,match="invalid_training_weight_lineage"):
        admit(candidate,base)


def test_legacy_windows_manifest_paths_and_alias_rejection(tmp_path):
    candidate,base=fixture(tmp_path)
    p=candidate/"candidate.json"
    record=json.loads(p.read_text())
    record["artifact_sha256"]={k.replace("/","\\"):v for k,v in record["artifact_sha256"].items()}
    p.write_text(json.dumps(record))
    assert admit(candidate,base)["peft_adapter_sha256"]==file_hash(candidate/"adapter/adapter_model.safetensors")
    record["artifact_sha256"]["adapter/adapter_model.safetensors"]=file_hash(candidate/"adapter/adapter_model.safetensors")
    p.write_text(json.dumps(record))
    with pytest.raises(ValueError,match="ambiguous_or_invalid_artifact_path"):
        admit(candidate,base)


def test_continued_training_requires_identical_base_lineage(tmp_path):
    from scripts.control_ai_adaptation import admit_parent_adapter
    candidate,base=fixture(tmp_path)
    hashes={p.name:file_hash(p) for p in base.iterdir()}
    adapter,lineage=admit_parent_adapter(candidate,base,"a"*40,hashes)
    assert adapter==candidate/"adapter"
    assert lineage["parent_trainable_sha256"]=="b"*64 and lineage["optimizer_continued"] is False
    with pytest.raises(ValueError,match="parent_training_base_mismatch"):
        admit_parent_adapter(candidate,base,"c"*40,hashes)
    with pytest.raises(ValueError,match="parent_training_base_mismatch"):
        admit_parent_adapter(candidate,base,"a"*40,dict(hashes,extra="d"*64))
    (candidate/"adapter"/"optimizer.pt").write_bytes(b"synthetic unsafe fixture")
    with pytest.raises(ValueError,match="unsafe_parent_adapter_format"):
        admit_parent_adapter(candidate,base,"a"*40,hashes)
