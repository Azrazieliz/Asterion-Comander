"""Private Asterion Control command recovery without duplicate execution."""
import json
from pathlib import Path

from asterion_remote import github_bridge_git as bridge


def test_private_active_queue_survives_legacy_migration(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "ROOT", tmp_path)
    monkeypatch.setattr(bridge, "STAMP", tmp_path / "bridge-migrated")
    published = []
    monkeypatch.setattr(bridge, "publish", lambda paths: published.extend(paths))
    commands = tmp_path / "commands"
    (commands / "active").mkdir(parents=True)
    (commands / "obsolete-legacy.json").write_text(
        json.dumps({"id": "obsolete-legacy", "op": "pc_status"}), encoding="utf8"
    )
    (commands / "active" / "owner-approved-update.json").write_text(
        json.dumps({"id": "owner-approved-update", "op": "pc_status"}), encoding="utf8"
    )
    bridge.migrate()
    legacy = json.loads(
        (tmp_path / "results" / "obsolete-legacy.json").read_text(encoding="utf8")
    )
    assert legacy["status"] == "skipped"
    assert not (tmp_path / "results" / "owner-approved-update.json").exists()
    assert [p.stem for p in bridge.entries()] == ["owner-approved-update"]
    assert bridge.STAMP.exists()
    assert published == [Path("results/obsolete-legacy.json")]


def test_private_active_queue_deduplicates_legacy_name(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "ROOT", tmp_path)
    commands = tmp_path / "commands"
    (commands / "active").mkdir(parents=True)
    (commands / "active" / "same-id.json").write_text("{}", encoding="utf8")
    (commands / "same-id.json").write_text("{}", encoding="utf8")
    assert [p.relative_to(commands).as_posix() for p in bridge.entries()] == [
        "active/same-id.json"
    ]
    (tmp_path / "results" / "same-id.json").write_text(
        '{"status":"running"}', encoding="utf8"
    )
    assert bridge.entries() == []


def test_explicit_reauthorization_prevents_initial_skip(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "ROOT", tmp_path)
    monkeypatch.setattr(bridge, "STAMP", tmp_path / "bridge-migrated")
    monkeypatch.setattr(bridge, "publish", lambda paths: None)
    commands = tmp_path / "commands"
    (commands / "active").mkdir(parents=True)
    for path in (commands / "owner-approved-update.json",
                 commands / "active" / "owner-approved-update.json"):
        path.write_text('{"id":"owner-approved-update","op":"pc_status"}',
                        encoding="utf8")
    bridge.migrate()
    assert not (tmp_path / "results" / "owner-approved-update.json").exists()
    assert [p.stem for p in bridge.entries()] == ["owner-approved-update"]


def test_running_receipt_is_durable_local_only_then_one_publication(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "ROOT", tmp_path)
    sent=[]
    monkeypatch.setattr(bridge,"publish",lambda files:sent.extend(files))
    identity="owner-fast-control-command"
    assert bridge.write_result(identity,{"id":identity,"status":"running"},
                               publish_now=False)
    assert sent==[]
    assert json.loads((tmp_path/"results"/(identity+".json")).read_text())["status"]=="running"
    assert bridge.write_result(identity,{"id":identity,"status":"complete","ok":True})
    assert sent==[Path("results")/(identity+".json")]
    assert json.loads((tmp_path/"results"/(identity+".json")).read_text())["ok"]
    assert not (tmp_path/"results"/(identity+".pending")).exists()


def test_failed_publication_recovers_finished_result_without_reexecution(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge,"ROOT",tmp_path)
    results=tmp_path/"results"
    results.mkdir()
    (results/"finished-unique.json").write_text(
        '{"id":"finished-unique","status":"complete","ok":true}',encoding="utf8")
    (results/"uncertain-inflight.json").write_text(
        '{"id":"uncertain-inflight","status":"running","ok":false}',encoding="utf8")
    (results/"not-a-command.txt").write_text("ignored",encoding="utf8")
    monkeypatch.setattr(bridge,"git",lambda *args:
        "?? results/finished-unique.json\n?? results/uncertain-inflight.json\n?? results/not-a-command.txt")
    published=[]
    monkeypatch.setattr(bridge,"publish",lambda paths: published.extend(paths))
    assert bridge.recover_unpublished()==1
    assert published==[Path("results/finished-unique.json")]


def test_pending_receipt_prevents_command_replay(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge,"ROOT",tmp_path)
    commands=tmp_path/"commands"/"active"
    commands.mkdir(parents=True)
    task=commands/"unique-write-intent.json"
    task.write_text('{"id":"unique-write-intent","op":"pc_status"}',encoding="utf8")
    assert len(bridge.entries())==1
    bridge.write_result("unique-write-intent",
                        {"id":"unique-write-intent","status":"running"},
                        publish_now=False)
    assert bridge.entries()==[]
