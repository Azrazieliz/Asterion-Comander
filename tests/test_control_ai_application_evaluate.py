import json
import shutil
import pytest
from scripts.control_ai_application_evaluate import cases,compile_probe,judge

@pytest.fixture(scope="module")
def compiled(tmp_path_factory):
    if not shutil.which("javac") or not shutil.which("java"):pytest.skip("JDK required")
    root=tmp_path_factory.mktemp("actual-parser")
    compile_probe(root)
    return root

def block(kind,lines):
    fence=chr(96)*3
    return fence+kind+"\n"+"\n".join(lines)+"\n"+fence

def test_application_judge_separates_valid_syntax_from_correct_values(compiled):
    case=cases()[0]
    good=judge(compiled,case,block("asterion_chart",["title|Stock remaining","bar|Cedar|9","bar|Willow|19"]))
    wrong=judge(compiled,case,block("asterion_chart",["title|Stock remaining","bar|Cedar|8","bar|Willow|19"]))
    malformed=judge(compiled,case,"I created a chart successfully.")
    assert good["passed"] and good["parser_accepted"] and good["content_correct"]
    assert wrong["parser_accepted"] and not wrong["content_correct"] and not wrong["passed"]
    assert not malformed["parser_accepted"] and not malformed["passed"]

def test_schedule_and_artifact_actual_parser_contracts(compiled):
    schedule=cases()[4]
    assert judge(compiled,schedule,block("asterion_schedule",["kind|reminder","title|Water plants","delay_minutes|120","interval_minutes|1440","prompt|Check soil moisture."]))["passed"]
    assert not judge(compiled,schedule,block("asterion_schedule",["kind|shell","title|Water plants","delay_minutes|120","interval_minutes|1440","prompt|Check soil moisture."]))["passed"]
    assert judge(compiled,cases()[7],block("csv",["name,note",'"A, B","Review, then approve"']))["passed"]
    assert not judge(compiled,cases()[7],block("csv",["name,note","A, B,Review, then approve"]))["passed"]

def test_application_suite_not_identical_to_training_cases():
    from scripts.control_ai_evidence_corpus import application_curriculum
    train,validation=application_curriculum()
    assert len({c["id"] for c in cases()})==10
    assert not {c["prompt"] for c in cases()}.intersection(r["messages"][-2]["content"] for r in train+validation)
