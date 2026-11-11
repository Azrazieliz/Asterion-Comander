"""Preserve real OAuth registrations/tokens when upgrading legacy SQLite column names."""
import sqlite3
from pathlib import Path
from asterion_remote import oauth_bridge

def test_legacy_schema_migrates_without_destroying_rows(tmp_path,monkeypatch):
    root=tmp_path/"control"
    root.mkdir()
    path=root/"oauth.sqlite3"
    with sqlite3.connect(str(path)) as db:
        db.execute("CREATE TABLE clients (client_id TEXT PRIMARY KEY, redirect_uris TEXT, created INTEGER)")
        db.execute("CREATE TABLE codes (hash TEXT PRIMARY KEY, client_id TEXT, redirect_uri TEXT, challenge TEXT, resource TEXT, expires INTEGER)")
        db.execute("CREATE TABLE tokens (hash TEXT PRIMARY KEY, kind TEXT, client_id TEXT, resource TEXT, expires INTEGER)")
        db.execute("INSERT INTO clients VALUES ('client-old','[]',1)")
        db.execute("INSERT INTO tokens VALUES ('digest-old','access','client-old','resource',1234567)")
    monkeypatch.setattr(oauth_bridge,"ROOT",root)
    monkeypatch.setattr(oauth_bridge,"DB_PATH",path)
    with oauth_bridge._db() as db:
        client=db.execute("SELECT redirects FROM clients").fetchone()
        token=db.execute("SELECT digest,kind FROM tokens").fetchone()
        cols=[x[1] for x in db.execute("PRAGMA table_info(codes)")]
        assert client==("[]",)
        assert token==("digest-old","access")
        assert "digest" in cols and "redirect" in cols
    # The migration is idempotent.
    with oauth_bridge._db() as db:
        assert db.execute("SELECT COUNT(*) FROM tokens").fetchone()[0]==1
