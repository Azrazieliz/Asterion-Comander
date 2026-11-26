"""Offline, dependency-free checks for genuine candidate adaptation prerequisites."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location(
    "control_ai_adaptation", ROOT/"scripts/control_ai_adaptation.py")
module=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def example(prompt):
    return {"domain":"coding","source":"owner-authored original",
            "rights_verified":True,
            "messages":[{"role":"user","content":prompt},
                        {"role":"assistant","content":"verified expected response"}]}


def test_untrained_candidate_pipeline_selftest():
    module.selftest()


def test_prompt_leakage_and_provenance(tmp_path):
    train=tmp_path/"train.jsonl"; hold=tmp_path/"hold.jsonl"
    train.write_text(json.dumps(example("Explain deterministic receipts")),encoding="utf8")
    hold.write_text(json.dumps(example(" Compare two valid receipts ")),encoding="utf8")
    assert module.validate(train,hold)[2]["maturity_certified"] is False
    hold.write_text(json.dumps(example(" EXPLAIN  deterministic   RECEIPTS ")),encoding="utf8")
    with pytest.raises(ValueError,match="contamination"):
        module.validate(train,hold)
    row=example("This has missing rights")
    row["rights_verified"]=False
    train.write_text(json.dumps(row),encoding="utf8")
    with pytest.raises(ValueError,match="rights"):
        module.read_examples(train)


def test_actual_weight_training_is_not_faked():
    assert hasattr(module,"train_adapter")
    assert "CUDA accelerator unavailable" in (ROOT/"scripts/control_ai_adaptation.py").read_text()


def test_cpu_diagnostic_is_explicit_and_default_fails_closed():
    assert module.training_device("cpu",False)=="cpu"
    with pytest.raises(RuntimeError,match="requires explicit"):
        module.training_device("auto",False)
    assert module.training_device("auto",True)=="cuda"
    with pytest.raises(ValueError):module.training_device("remote",True)


def test_owner_corpus_targets_have_exact_source_spans_and_no_teacher_outputs(tmp_path):
    from scripts.control_ai_owner_corpus import build
    metadata=build(tmp_path)
    source=(tmp_path/"owner-quotations.txt").read_text()
    for split in ("train.jsonl","holdout.jsonl"):
        for _,row in module.read_examples(tmp_path/split):
            if row["target_origin"]=="verbatim_owner_instruction":
                assert source[row["source_char_start"]:row["source_char_end"]]==row["messages"][-1]["content"]
    _,_,receipt=module.validate(tmp_path/"train.jsonl",tmp_path/"holdout.jsonl")
    assert receipt["training"]["count"]==20
    assert receipt["holdout"]["count"]==12
    assert not metadata["proprietary_teacher_outputs"]
    assert not receipt["maturity_certified"]
