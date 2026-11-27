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
