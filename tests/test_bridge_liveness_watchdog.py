"""Regression: private Control queue supervision is based on progress, never
mere process existence. No real phone, owner credentials or Windows tasks touched.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest
from asterion_remote import github_bridge_git as worker

ROOT=Path(__file__).resolve().parents[1]
WATCHDOG=(ROOT/"scripts/control_repair_watchdog.ps1").read_text("utf8")
LEGACY=(ROOT/"asterion_remote/github_bridge.py").read_text("utf8")
GIT_WORKER=(ROOT/"asterion_remote/github_bridge_git.py").read_text("utf8")


def prepare(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, "ROOT", tmp_path)
    monkeypatch.setattr(worker, "HEALTH", tmp_path/"control-git-bridge-health.json")
    monkeypatch.setattr(worker, "HEALTH_STATE", {
        "phase":"starting", "last_sync_utc":None,
        "last_publish_utc":None, "inflight_id":None,
        "pending_count":None, "consecutive_errors":0})
    monkeypatch.setattr(worker, "git", lambda *args, **kwargs: "")
    monkeypatch.setattr(worker, "publish", lambda paths: None)
    monkeypatch.setattr(worker, "ensure_agent", lambda key: {"ok":True})
    (tmp_path/"commands"/"active").mkdir(parents=True)


def test_atomic_heartbeat_does_not_leak_command_arguments(tmp_path, monkeypatch):
    prepare(tmp_path,monkeypatch)
    worker.health("idle",pending_count=27,last_sync_utc="2026-11-16T13:00:00+00:00")
    file=tmp_path/"control-git-bridge-health.json"
    value=json.loads(file.read_text("utf8"))
    assert value["transport"]=="private_git"
    assert value["pending_count"]==27
    assert value["inflight_id"] is None
    assert value["schema"]==1
    assert value["pid"]>0
    assert "heartbeat_utc" in value
    with pytest.raises(ValueError):
        worker.health("idle",token="DO_NOT_WRITE_SECRETS")
    with pytest.raises(ValueError):
        worker.health("unsupported")


def test_active_command_emits_sync_and_final_receipt_without_replay(tmp_path,monkeypatch):
    prepare(tmp_path,monkeypatch)
    command=tmp_path/"commands"/"active"/"live-readonly-status.json"
    command.write_text(json.dumps({
        "id":"live-readonly-status",
        "op":"pc_status","params":{}}),encoding="utf8")
    calls=[]
    def invoke(request,key):
        calls.append(request["id"])
        return {"ok":True}
    monkeypatch.setattr(worker, "run", invoke)
    assert worker.cycle("redacted-key")==1
    record=json.loads((tmp_path/"results"/command.name).read_text("utf8"))
    assert record["status"]=="complete"
    assert record["ok"] is True
    health=json.loads((tmp_path/"control-git-bridge-health.json").read_text("utf8"))
    assert health["phase"]=="idle"
    assert health["last_sync_utc"] is not None
    assert health["last_publish_utc"] is not None
    assert health["inflight_id"] is None
    assert health["pending_count"]==0
    assert worker.cycle("redacted-key")==0
    assert calls==["live-readonly-status"]


def test_uncertain_inflight_action_is_not_replayed_on_next_cycle(tmp_path,monkeypatch):
    prepare(tmp_path,monkeypatch)
    active=tmp_path/"commands"/"active"
    file=active/"recorded-side-effect.json"
    file.write_text(json.dumps({
        "id":"recorded-side-effect","op":"pc_command",
        "params":{"command":"echo no_replay"}}),encoding="utf8")
    result=tmp_path/"results"
    result.mkdir()
    (result/file.name).write_text(json.dumps({
        "id":"recorded-side-effect","status":"running","ok":False}),encoding="utf8")
    monkeypatch.setattr(worker, "run",
        lambda *args,**kwargs: pytest.fail("Uncertain side effect replayed"))
    assert worker.cycle("redacted-key")==0
    saved=json.loads((result/file.name).read_text("utf8"))
    assert saved["status"]=="uncertain"


def test_watchdog_checks_bridge_before_native_api_failure_short_circuit():
    assert WATCHDOG.index("$bridge=@(")<WATCHDOG.index("$missesFile=")
    assert WATCHDOG.index("$bridge=@(")<WATCHDOG.index("if($misses -lt 3){exit 0}")
    assert "control-git-bridge-health.json" in WATCHDOG
    assert "$ageSeconds -ge 360" in WATCHDOG
    assert "$errorCount -ge 4" in WATCHDOG
    assert "if(-not [string]::IsNullOrWhiteSpace($inflight))" in WATCHDOG
    assert "$jobsKnown -and -not $activeJobs -and $cooldown" in WATCHDOG
    assert "$bridge.Count -gt 1" in WATCHDOG
    assert "control-git-bridge-last-recovery.txt" in WATCHDOG


def test_deprecated_rest_relay_cannot_ignore_active_queue():
    assert "from .github_bridge_git import main as git_main" in LEGACY
    assert "git_main()" in LEGACY
    assert "commands/'active'" in GIT_WORKER
    assert "git('clone','--quiet','--depth','1','--single-branch'," in GIT_WORKER
    assert "health('processing',inflight_id=identity)" in GIT_WORKER
    assert "health('retrying',consecutive_errors=failures" in GIT_WORKER


def test_backup_and_pairing_are_not_changed_by_watchdog():
    for forbidden in ("Remove-Item $key","Remove-Item $hostFile",
                      "Remove-Item $secret","adb ","-Recurse -Force"):
        assert forbidden not in WATCHDOG
    assert "Stop-Process -Id $current.ProcessId -Force" in WATCHDOG
    assert "Stop-Process -Id $worker" not in WATCHDOG
