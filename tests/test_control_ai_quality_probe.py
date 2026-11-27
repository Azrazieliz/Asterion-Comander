import json
from scripts.control_ai_quality_probe import cases
from asterion_remote.model_evaluation import _score

def test_quality_fixture_answers_are_valid_and_unique():
    rows=cases()
    assert len(rows)==12
    assert len({r["id"] for r in rows})==len(rows)
    assert len({r["prompt"] for r in rows})==len(rows)
    assert len({r["category"] for r in rows})>=9
    for row in rows:
        assert _score(row,json.dumps(row["expected"]),None)[0]=="passed"
        assert _score(row,"{}",None)[0]=="failed"
