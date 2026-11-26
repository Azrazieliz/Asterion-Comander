"""Lifecycle regressions for the real independent daemon, without fake AI progress."""
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from asterion_remote import dev_backlog, overnight_supervisor
from scripts import control_ai_autonomous_daemon as daemon

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def setup(tmp_path):
    repo=tmp_path/"control-source"
    repo.mkdir()
    (repo/".git").mkdir()
    docs=repo/"docs"
    docs.mkdir()
    manifest=json.loads((ROOT/"docs/CONTROL_NATIVE_AI_BACKLOG_20261126.json")
                        .read_text(encoding="utf-8"))
    (docs/"CONTROL_NATIVE_AI_BACKLOG_20261126.json").write_text(
        json.dumps(manifest),encoding="utf-8")
    config={
        "repo":str(repo),
        "tasks":"docs/CONTROL_NATIVE_AI_BACKLOG_20261126.json",
        "cycle":"native_daemon_test_20261126",
        "isolated_root":str(tmp_path/"isolated"),
        "endpoint":"http://127.0.0.1:8080/v1/chat/completions",
        "model":"local",
        "pinned_test_image":"sha256:"+"0"*64,
        "reviewed_test_map":manifest["trusted_tests"],
        "status_file":str(tmp_path/"status.json")
    }
    with patch.dict(os.environ,{"ASTERION_OVERNIGHT_ROOT":str(tmp_path/"state")}):
        yield config, tmp_path


def test_missing_local_model_or_container_never_claims_work(setup,monkeypatch):
    config,root=setup
    def blocked(_):
        raise RuntimeError("isolated_container_not_available")
    monkeypatch.setattr(daemon,"preflight",blocked)
    first=daemon.run(config,once=True)
    assert first["state"]=="blocked_prerequisites"
    assert first["verified_turns"]==0
    assert overnight_supervisor.status(config["cycle"])["state"]=="ready"
    assert all(t["state"]=="pending" for t in dev_backlog.snapshot(config["cycle"]))
    # A second fresh invocation resumes the SAME state, not a duplicate cycle.
    second=daemon.run(config,once=True)
    assert second["state"]=="blocked_prerequisites"
    assert len(dev_backlog.snapshot(config["cycle"]))==len(
        json.loads((ROOT/"docs/CONTROL_NATIVE_AI_BACKLOG_20261126.json")
                   .read_text())["tasks"])
    status=json.loads(Path(config["status_file"]).read_text())
    assert status["state"]=="blocked_prerequisites"
    assert "endpoint" not in status
    assert "model" not in status


def test_uncertain_turn_stays_blocked_after_process_restart(setup,monkeypatch):
    config,root=setup
    daemon.initialize(config["cycle"],
        Path(config["repo"])/config["tasks"])
    claimed=overnight_supervisor.claim(config["cycle"])
    assert claimed["state"]=="dispatch_uncertain"
    monkeypatch.setattr(daemon,"preflight",
                        lambda c:pytest.fail("uncertain source may not replay"))
    result=daemon.run(config,once=True)
    assert result["state"]=="dispatch_uncertain"
    assert overnight_supervisor.status(config["cycle"])["turn_index"]==1
    assert dev_backlog.claim(config["cycle"]) is not None  # no candidate generated yet


def test_config_reviewed_tests_are_immutable(setup):
    config,root=setup
    config["reviewed_test_map"]={"fake":["tests/test_control_ai_executor.py"]}
    with pytest.raises(ValueError,match="trusted_test_map_changed"):
        daemon.run(config,once=True)
