import sqlite3

import pytest

from asterion_remote import skill_studio, interaction_sessions


def create(description):
    return skill_studio.create("test:skill",description,"pc",[{"kind":"health"}])


def test_versions_rollback_and_reapproval(tmp_path,monkeypatch):
    monkeypatch.setenv("ASTERION_SKILL_STUDIO_ROOT",str(tmp_path))
    first=create("First definition")
    skill_studio.approve(first["id"],first["sha256"])
    second=create("Second definition")
    assert [v["version"] for v in skill_studio.versions(first["id"])["versions"]]==[2,1]
    with pytest.raises(ValueError,match="current_definition_changed"):
        skill_studio.rollback(first["id"],1,first["sha256"])
    rolled=skill_studio.rollback(first["id"],1,second["sha256"])
    assert rolled["version"]==3 and rolled["sha256"]==first["sha256"]
    assert skill_studio.details(first["id"])["state"]=="draft"
    with pytest.raises(PermissionError):
        skill_studio.execute(first["id"],first["sha256"],"skill-test-001")
    skill_studio.approve(first["id"],first["sha256"])
    calls=[]
    def start(session):
        calls.append(session)
        return {"ok":True,"id":"actual-session-test","reused":False}
    monkeypatch.setattr(interaction_sessions,"start",start)
    result=skill_studio.execute(first["id"],first["sha256"],"skill-test-001")
    assert result["session"]["id"]=="actual-session-test" and len(calls)==1
    assert calls[0].steps[0].kind=="health"


def test_reject_tampered_definition_and_historical_version(tmp_path,monkeypatch):
    monkeypatch.setenv("ASTERION_SKILL_STUDIO_ROOT",str(tmp_path))
    first=create("First definition")
    second=create("Second definition")
    skill_studio.approve(second["id"],second["sha256"])
    with sqlite3.connect(tmp_path/"skills.sqlite3") as db:
        db.execute("UPDATE skill_versions SET definition='{}' WHERE version=1")
        db.execute("UPDATE skills SET definition='{}'")
    with pytest.raises(PermissionError,match="integrity_failed"):
        skill_studio.execute(second["id"],second["sha256"],"skill-test-002")
    with pytest.raises(ValueError,match="integrity_failed"):
        skill_studio.rollback(second["id"],1,second["sha256"])


def test_old_database_migration_preserves_current_version(tmp_path,monkeypatch):
    monkeypatch.setenv("ASTERION_SKILL_STUDIO_ROOT",str(tmp_path))
    first=create("First definition")
    with sqlite3.connect(tmp_path/"skills.sqlite3") as db:
        db.execute("DROP TABLE skill_versions")
    assert skill_studio.versions(first["id"])["versions"][0]["sha256"]==first["sha256"]
    second=create("Second definition")
    assert second["version"]==2
    assert len(skill_studio.versions(first["id"])["versions"])==2
