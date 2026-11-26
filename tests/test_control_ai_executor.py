"""Synthetic local git acceptance for candidate executor; no production promotion.

A fake test runner is used only to exercise receipt plumbing, NOT to certify
that a real isolated container exists on the owner's Windows PC.
"""
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from asterion_remote.independent_dev_executor import CandidateExecutor, source_context

SHA=hashlib.sha256(b"synthetic-isolated-test-receipt").hexdigest()


def git(path,*args):
    return subprocess.run(["git","-C",str(path),*args],check=True,
                          stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                          text=True).stdout.strip()


@pytest.fixture
def prepared(tmp_path):
    root=tmp_path/"canonical"
    root.mkdir()
    git(root,"init","-q")
    git(root,"config","user.email","local-synthetic@example.invalid")
    git(root,"config","user.name","synthetic")
    target=root/"asterion_remote"/"trial.py"
    target.parent.mkdir()
    target.write_text("value = 1\n",encoding="utf-8")
    git(root,"add",".")
    git(root,"commit","-m","verified test fixture")
    task={"task_id":"testsource01","target_path":"asterion_remote/trial.py",
          "goal":"Correct isolated test source and preserve canonical data"}
    return root,tmp_path/"candidate-worktrees",task,target


def proposal(task,target,*,value="value = 2\n",change_target=False):
    return json.dumps({"task_id":task["task_id"],
        "target_path":"scripts/forbidden.py" if change_target else task["target_path"],
        "expected_sha256":hashlib.sha256(target.read_bytes()).hexdigest(),
        "replacement":value,"next_work":"Continue with independent evaluation tests"})


def test_no_host_execution_when_container_not_verified(prepared):
    repo,scratch,task,target=prepared
    executor=CandidateExecutor(repo,scratch)
    with pytest.raises(RuntimeError,match="sandbox_not_verified"):
        executor.run(proposal(task,target),"testcycle01","testcycle01-turn-1",task)
    assert target.read_text()=="value = 1\n"
    assert (scratch/"testcycle01-turn-1"/"asterion_remote/trial.py").read_text()=="value = 2\n"


def test_scoped_edits_and_exact_hashes(prepared):
    repo,scratch,task,target=prepared
    executor=CandidateExecutor(repo,scratch)
    with pytest.raises(ValueError,match="out_of_scope"):
        executor.run(proposal(task,target,change_target=True),"testcycle01",
                     "testcycle01-turn-2",task)
    assert not (scratch/"testcycle01-turn-2").exists()
    with pytest.raises(ValueError,match="invalid_replacement"):
        executor.run(proposal(task,target,value=""),"testcycle01",
                     "testcycle01-turn-3",task)


def test_real_candidate_commit_with_synthetic_test_gate(prepared):
    repo,scratch,task,target=prepared
    def fake_isolated_gate(*args):
        assert args[0].is_dir()
        return {"exit_code":0,"runner_kind":"isolated_container",
                "receipt_sha256":SHA}
    executor=CandidateExecutor(repo,scratch,sandbox_test=fake_isolated_gate)
    evidence=executor.run(proposal(task,target),"testcycle01",
                          "testcycle01-turn-4",task)
    assert len(evidence["candidate_commit"])==40
    assert evidence["evidence_sha256"] != SHA
    assert evidence["verification_level"]=="source_tested"
    assert evidence["done"] is False
    assert target.read_text()=="value = 1\n"
    assert (scratch/"testcycle01-turn-4"/"asterion_remote/trial.py").read_text()=="value = 2\n"


def test_grounded_context_contains_exact_sha(prepared):
    repo,scratch,task,target=prepared
    payload=json.loads(source_context(repo,task))
    assert payload["sha256"]==hashlib.sha256(target.read_bytes()).hexdigest()
    assert payload["source"]=="value = 1\n"
