"""Regression checks for authenticated, non-destructive full-path Control recovery."""
import json
import time
from fastapi.testclient import TestClient
from asterion_remote.app import app
from asterion_remote.security import configured_token
from asterion_remote import recovery

AUTH = {"Authorization": "Bearer "+configured_token()}


def test_recovery_requires_authorization():
    with TestClient(app) as client:
        assert client.get("/api/v1/recovery/status").status_code == 401
        assert client.post("/api/v1/recovery/start", json={"mode": "auto"}).status_code == 401


def test_recovery_starts_fixed_script_once_and_persists_receipt(tmp_path, monkeypatch):
    script = tmp_path / "scripts" / "control_full_repair.ps1"
    script.parent.mkdir(parents=True)
    script.write_text("# approved fixed recovery action\n", encoding="utf-8")
    state = tmp_path / "state"
    captured = []
    monkeypatch.setattr(recovery, "ROOT", tmp_path)
    monkeypatch.setattr(recovery, "STATE", state)
    monkeypatch.setattr(recovery, "REPORT", state / "full-repair.json")
    monkeypatch.setattr(recovery.subprocess, "Popen",
                        lambda args, **kw: captured.append((args, kw)) or object())
    with TestClient(app) as client:
        response = client.post("/api/v1/recovery/start", headers=AUTH, json={"mode": "auto"})
        assert response.status_code == 202, response.text
        ticket = response.json()["id"]
        assert response.json()["ok"] is False
        assert captured[0][0][-4:] == ["-Mode", "auto", "-RepairId", ticket]
        assert str(script) in captured[0][0]
        assert client.get("/api/v1/recovery/status", headers=AUTH).json()["id"] == ticket
        assert client.post("/api/v1/recovery/start", headers=AUTH,
                           json={"mode": "force"}).status_code == 409
        assert client.post("/api/v1/recovery/start", headers=AUTH,
                           json={"mode": "arbitrary_shell"}).status_code == 422
    saved = json.loads((state / "full-repair.json").read_text())
    assert saved["phase"] == "running"
    assert "token" not in json.dumps(saved).lower()


def test_stale_recovery_is_not_claimed_successful(tmp_path, monkeypatch):
    monkeypatch.setattr(recovery, "REPORT", tmp_path / "report.json")
    recovery.REPORT.write_text(json.dumps({"id": "old", "phase": "running",
                                            "updated": time.time()-200, "ok": False}))
    with TestClient(app) as client:
        receipt = client.get("/api/v1/recovery/status", headers=AUTH).json()
        assert receipt["phase"] == "stale"
        assert receipt["ok"] is False
