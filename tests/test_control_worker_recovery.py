"""Concrete failure/restart cases for the private Asterion Control Windows worker."""
import json
from pathlib import Path
import pytest

from asterion_remote import github_bridge_git as control


def prepare(tmp_path, monkeypatch):
    monkeypatch.setattr(control, "ROOT", tmp_path)
    monkeypatch.setattr(control, "git", lambda *args, **kwargs: "")
    monkeypatch.setattr(control, "publish", lambda paths: None)
    monkeypatch.setattr(control, "ensure_agent", lambda key: {"ok": True})
    active = tmp_path / "commands" / "active"
    active.mkdir(parents=True)
    return active


def test_native_private_ip_resolves_dynamically(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    directory = tmp_path / "AsterionControl"
    directory.mkdir()
    host = directory / "agent-host.txt"
    host.write_text("http://192.168.12.48:8911", encoding="utf8")
    assert control.agent_host() == "http://192.168.12.48:8911"
    host.write_text("http://10.2.0.23:8911", encoding="utf8")
    assert control.agent_host() == "http://10.2.0.23:8911"


@pytest.mark.parametrize("url", [
    "http://0.0.0.0:8911", "http://1.2.3.4:8911",
    "https://192.168.1.2:8911", "http://192.168.1.2:9999",
    "http://169.254.4.5:8911", "http://127.0.0.1:8911@evil.example",
    "http://192.168.1.2:8911/control",
])
def test_native_endpoint_refuses_unauthorized_addresses(tmp_path, monkeypatch, url):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    directory = tmp_path / "AsterionControl"
    directory.mkdir()
    (directory / "agent-host.txt").write_text(url, encoding="utf8")
    with pytest.raises(RuntimeError):
        control.agent_host()


def test_agent_offline_cannot_consume_private_command(tmp_path, monkeypatch):
    active = prepare(tmp_path, monkeypatch)
    (active / "owner-build-checkpoint.json").write_text(
        '{"id":"owner-build-checkpoint","op":"pc_command","params":{"command":"echo safe"}}',
        encoding="utf8",
    )
    monkeypatch.setattr(control, "ensure_agent",
                        lambda key: (_ for _ in ()).throw(ConnectionError("Control offline")))
    with pytest.raises(ConnectionError):
        control.cycle("private-key")
    assert not (tmp_path / "results" / "owner-build-checkpoint.json").exists()


@pytest.mark.parametrize("exit_code,expected", [(0, "complete"), (1, "error")])
def test_native_async_job_requires_real_exit_receipt(tmp_path, monkeypatch, exit_code, expected):
    active = prepare(tmp_path, monkeypatch)
    command = active / "owner-approved-build.json"
    command.write_text(json.dumps({
        "id": "owner-approved-build", "op": "pc_command",
        "params": {"command": "powershell.exe -File safe.ps1"},
    }), encoding="utf8")
    jobid = "a" * 32
    calls = []

    def dispatch(request, key):
        calls.append(request["op"])
        if request["op"] == "pc_command":
            return {"id": jobid, "status": "running"}
        if request["op"] == "pc_job_status":
            return {"id": jobid, "status": "finished", "exit_code": exit_code,
                    "output": "Execution evidence"}
        raise AssertionError(request)

    monkeypatch.setattr(control, "run", dispatch)
    assert control.cycle("private-key") == 1
    result = tmp_path / "results" / "owner-approved-build.json"
    accepted = json.loads(result.read_text(encoding="utf8"))
    assert accepted["status"] == "accepted"
    assert accepted["result"]["id"] == jobid
    assert control.cycle("private-key") == 0
    final = json.loads(result.read_text(encoding="utf8"))
    assert final["status"] == expected
    assert final["ok"] is (exit_code == 0)
    assert final["result"]["exit_code"] == exit_code
    assert calls == ["pc_command", "pc_job_status"]


def test_unreturned_job_receipt_never_replays_side_effect(tmp_path, monkeypatch):
    prepare(tmp_path, monkeypatch)
    results = tmp_path / "results"
    results.mkdir(exist_ok=True)
    pending = results / "interrupted-build.json"
    pending.write_text(
        json.dumps({"id": "interrupted-build", "status": "running", "ok": False}),
        encoding="utf8")
    monkeypatch.setattr(control, "run", lambda req, key: pytest.fail("Must not replay"))
    assert control.cycle("private-key") == 0
    record = json.loads(pending.read_text(encoding="utf8"))
    assert record["status"] == "uncertain"
    assert not record["ok"]


def test_native_batch_publishes_three_final_receipts_in_one_push(tmp_path, monkeypatch):
    active = prepare(tmp_path, monkeypatch)
    published = []
    monkeypatch.setattr(control, "publish", lambda paths: published.append(list(paths)))
    monkeypatch.setattr(control, "run", lambda req, key: {"ok": True, "source": req["id"]})
    for i in range(3):
        identity = f"read-only-batch-{i}"
        (active / f"{identity}.json").write_text(
            json.dumps({"id": identity, "op": "pc_status", "params": {}}), encoding="utf8")
    assert control.cycle("private-key") == 3
    assert len(published) == 1
    assert len(published[0]) == 3
    for i in range(3):
        identity = f"read-only-batch-{i}"
        receipt = json.loads((tmp_path / "results" / f"{identity}.json").read_text("utf8"))
        assert receipt["ok"] is True
        assert receipt["status"] == "complete"
        assert receipt["result"]["source"] == identity


def test_native_batch_has_bounded_twelve_command_window(tmp_path, monkeypatch):
    active = prepare(tmp_path, monkeypatch)
    published = []
    executed = []
    monkeypatch.setattr(control, "publish", lambda paths: published.append(list(paths)))
    monkeypatch.setattr(control, "run", lambda req, key: executed.append(req["id"]) or {"ok": True})
    for i in range(13):
        identity = f"bounded-batch-{i:02d}"
        (active / f"{identity}.json").write_text(
            json.dumps({"id": identity, "op": "pc_status", "params": {}}), encoding="utf8")
    assert control.cycle("private-key") == 12
    assert len(published) == 1 and len(published[0]) == 12
    assert len(executed) == 12
    assert control.cycle("private-key") == 1
    assert len(published) == 2 and len(published[1]) == 1
    assert len(executed) == 13
