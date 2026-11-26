"""Persistent task dependency and no-double-dispatch regressions; no production edits."""
import hashlib
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import pytest

from asterion_remote import dev_backlog, overnight_supervisor

DIGEST=hashlib.sha256(b"non-production-synthetic-evidence").hexdigest()
COMMIT="a"*40


def item(key,dep=()):
    return {"id":key,"priority":0,"component":"Control AI",
            "goal":"Implement actual dependency-checked source behavior",
            "target_path":"asterion_remote/model_evaluation.py",
            "depends_on":list(dep)}


@pytest.fixture
def cycle():
    with tempfile.TemporaryDirectory() as d:
        with patch.dict(os.environ,{"ASTERION_OVERNIGHT_ROOT":d}):
            overnight_supervisor.create("testrecovery01","AsterionControl",
                "docs/source.md","Maintain trustworthy test execution")
            yield "testrecovery01"


def test_dependency_order_and_durable_state(cycle):
    dev_backlog.seed(cycle,[item("taskfirst"),item("tasksecond",["taskfirst"])])
    assert len(dev_backlog.snapshot(cycle))==2
    first=dev_backlog.claim(cycle)
    assert first["task_id"]=="taskfirst"
    assert dev_backlog.claim(cycle) is None
    dev_backlog.record(first["task_id"],evidence_sha256=DIGEST,
                       candidate_commit=COMMIT,verification_level="source_tested")
    second=dev_backlog.claim(cycle)
    assert second["task_id"]=="tasksecond"
    assert second["attempt"]==1
    assert dev_backlog.claim(cycle) is None
    assert dev_backlog.snapshot(cycle)[0]["verification_level"]=="source_tested"


def test_exactly_once_claim_and_fail_closed_crash(cycle):
    dev_backlog.seed(cycle,[item("taskfirst")])
    with ThreadPoolExecutor(max_workers=6) as pool:
        requests=list(pool.map(lambda _:dev_backlog.claim(cycle),range(6)))
    assert sum(r is not None for r in requests)==1
    assert dev_backlog.claim(cycle) is None
    dev_backlog.block("taskfirst","missing_isolation")
    assert dev_backlog.snapshot(cycle)[0]["state"]=="needs_review"
    assert dev_backlog.claim(cycle) is None


def test_atomic_seed_preserves_prior_work_and_rejects_ghost_dependency(cycle):
    dev_backlog.seed(cycle,[item("taskfirst")])
    with pytest.raises(ValueError,match="unknown_task_dependency"):
        dev_backlog.seed(cycle,[item("taskghost",["absenttask"])])
    assert len(dev_backlog.snapshot(cycle))==1
    dev_backlog.seed(cycle,[item("taskfirst")])
    with pytest.raises(ValueError,match="existing_task"):
        changed=item("taskfirst")
        changed["goal"]="Changed existing owner specification is disallowed"
        dev_backlog.seed(cycle,[changed])


def test_receipt_cannot_forge_device_acceptance(cycle):
    dev_backlog.seed(cycle,[item("taskfirst")])
    dev_backlog.claim(cycle)
    with pytest.raises(ValueError,match="device_acceptance"):
        dev_backlog.record("taskfirst",evidence_sha256=DIGEST,
                           candidate_commit=COMMIT,verification_level="device_verified")
    with pytest.raises(ValueError,match="invalid_independent_source_receipt"):
        dev_backlog.record("taskfirst",evidence_sha256="0",
                           candidate_commit=COMMIT,verification_level="source_tested")


def test_cyclic_dependency_graph_is_rejected(cycle):
    with pytest.raises(ValueError,match="cyclic_task_dependencies"):
        dev_backlog.seed(cycle,[item("taskfirst",["tasksecond"]),item("tasksecond",["taskfirst"])])
    assert dev_backlog.snapshot(cycle)==[]

def test_independent_tasks_cannot_claim_same_cycle_concurrently(cycle):
    dev_backlog.seed(cycle,[item("taskfirst"),item("tasksecond")])
    with ThreadPoolExecutor(max_workers=6) as pool:
        claims=list(pool.map(lambda _:dev_backlog.claim(cycle),range(6)))
    assert sum(c is not None for c in claims)==1

def test_priority_is_not_silently_rewritten(cycle):
    original=item("taskfirst")
    dev_backlog.seed(cycle,[original])
    with pytest.raises(ValueError,match="existing_task"):
        dev_backlog.seed(cycle,[dict(original,priority=9)])
