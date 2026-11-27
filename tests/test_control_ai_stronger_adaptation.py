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
