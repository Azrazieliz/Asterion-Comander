from scripts.control_ai_stronger_adaptation import corpus
from scripts.control_ai_quality_probe import cases
from scripts.control_ai_adaptation import validate
import json

def test_stronger_public_fixture_separation(tmp_path):
    train,hold=corpus()
    for name,rows in (("train",train),("hold",hold)):
        (tmp_path/name).write_text("".join(json.dumps(x)+"\n" for x in rows))
    _,_,summary=validate(tmp_path/"train",tmp_path/"hold")
    assert summary["training"]["count"]==17
    assert summary["holdout"]["count"]==4
    prompts={x["messages"][-2]["content"] for x in train+hold}
    assert not prompts.intersection(x["prompt"] for x in cases())
    assert not summary["maturity_certified"]


def test_application_curriculum_has_native_protocol_targets_and_separate_families(tmp_path):
    from scripts.control_ai_evidence_corpus import application_curriculum,application_preferences
    from scripts.control_ai_preferences import read_preferences
    train,hold=application_curriculum()
    assert len(train)==128 and len(hold)==24
    assert {x["workflow_family"] for x in train}.isdisjoint(x["workflow_family"] for x in hold)
    assert len({x["domain"] for x in train})>=12
    assert not {x["messages"][-2]["content"] for x in train+hold}.intersection(x["prompt"] for x in cases())
    for name,rows in (("train",train),("holdout",hold),("preferences",application_preferences(train))):
        (tmp_path/name).write_text("".join(json.dumps(x)+"\n" for x in rows))
    a,b,summary=validate(tmp_path/"train",tmp_path/"holdout")
    assert len(read_preferences(tmp_path/"preferences",a,b))==56
    assert not summary["maturity_certified"]
    fence=chr(96)*3
    for row in train:
        family=row["workflow_family"];answer=row["messages"][-1]["content"]
        if family.startswith("native-") and family!="native-transfer-recovery":
            assert answer.startswith(fence) and answer.endswith("\n"+fence)
            if family=="native-signed-proposal":
                assert set(json.loads(answer.splitlines()[1]))=={"package","action","payload"}


def test_accelerated_training_is_default_and_cpu_requires_explicit_budget():
    import pytest
    from scripts.control_ai_stronger_adaptation import parse_args, step_budget
    a=parse_args(["output","--curriculum"])
    assert a.device=="cuda" and a.phase=="train"
    assert step_budget(a.device,a.curriculum,a.steps)==48
    with pytest.raises(ValueError,match="explicit diagnostic"):
        step_budget("cpu",True,None)
    assert step_budget("cpu",True,1)==1
    for steps in (0,-1,10001):
        with pytest.raises(ValueError,match="invalid_step_budget"):
            step_budget("cuda",True,steps)

def test_memory_admission_requires_actual_accelerator_and_host_budget():
    import pytest
    from scripts.control_ai_stronger_adaptation import memory_admission
    GiB=1<<30
    memory_admission(5*GiB,7*GiB,10*GiB,"cuda",9*GiB)
    for accelerator in (None,7*GiB):
        with pytest.raises(RuntimeError,match="cuda_training_memory"):
            memory_admission(5*GiB,10*GiB,10*GiB,"cuda",accelerator)
    with pytest.raises(RuntimeError,match="host_staging"):
        memory_admission(5*GiB,5*GiB,10*GiB,"cuda",9*GiB)
    with pytest.raises(RuntimeError,match="training_disk"):
        memory_admission(5*GiB,10*GiB,6*GiB,"cuda",9*GiB)
    with pytest.raises(RuntimeError,match="cpu_training_memory"):
        memory_admission(5*GiB,7*GiB,10*GiB,"cpu")
