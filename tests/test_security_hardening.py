import hashlib
import json
import os
import stat
import zipfile
import pytest
from asterion_remote import security_scanner as s

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def test_deep_reads_archive_content_and_reports_unsupported_nested(tmp_path):
    p=tmp_path/"a.zip"
    with zipfile.ZipFile(p,"w") as z:
        z.writestr("a.txt",b"data")
    result=s.scan(p,level="deep",antivirus="")
    assert result["archive"]["content_bytes_verified"]==4
    assert result["archive"]["deep_content_complete"] is True
    assert result["verdict"]=="incomplete"
    with zipfile.ZipFile(p,"w") as z:
        z.writestr("inner.zip",b"not inspected recursively")
    assert s.scan(p,level="deep",antivirus="")["archive"]["deep_content_complete"] is False

def test_zip_alias_symlink_and_macro_flags(tmp_path):
    p=tmp_path/"a.zip"
    with zipfile.ZipFile(p,"w") as z:
        z.writestr("Name.txt",b"a")
        z.writestr("name.TXT",b"b")
        link=zipfile.ZipInfo("link");link.create_system=3
        link.external_attr=(stat.S_IFLNK|0o777)<<16
        z.writestr(link,"../secret")
        z.writestr("word/vbaProject.bin",b"macro")
    result=s.scan(p,level="deep",antivirus="")
    assert {"archive_duplicate_or_alias_path","archive_contains_symlink","archive_contains_macro_project"} <= set(result["findings"])

def test_no_overwrite_and_reconcile_after_restore_crash(tmp_path):
    p=tmp_path/"source.txt";p.write_bytes(b"original");digest=sha(p)
    root=tmp_path/"state";receipt=s.quarantine(p,root,digest)
    p.write_bytes(b"unrelated")
    with pytest.raises(FileExistsError):s.restore(receipt["id"],root)
    assert p.read_bytes()==b"unrelated"
    p.unlink()
    vault=root/"quarantine";blob=vault/(receipt["id"]+".blob")
    s._rename_noreplace(blob,p) # simulate crash after atomic restore
    assert s.inventory(root)["items"][0]["state"]=="recovery_required"
    result=s.restore(receipt["id"],root)
    assert result["reconciled"] and sha(p)==digest
    assert not s.inventory(root)["items"]

def test_restore_policy_rechecked(tmp_path):
    p=tmp_path/"source.txt";p.write_bytes(b"original")
    root=tmp_path/"state";receipt=s.quarantine(p,root,sha(p))
    with pytest.raises(ValueError,match="restore_destination_changed"):
        s.restore(receipt["id"],root,authorize=lambda p:tmp_path/"other")
    assert not p.exists()
    assert s.inventory(root)["items"][0]["state"]=="quarantined"

def test_hardlink_rejected_and_no_replace_primitive(tmp_path):
    p=tmp_path/"source";p.write_bytes(b"source")
    q=tmp_path/"other";q.write_bytes(b"other")
    with pytest.raises(FileExistsError):s._rename_noreplace(p,q)
    assert p.read_bytes()==b"source" and q.read_bytes()==b"other"
    link=tmp_path/"alias";os.link(p,link)
    with pytest.raises(ValueError,match="regular_unlinked"):
        s.quarantine(p,tmp_path/"state",sha(p))
    assert p.exists() and link.exists()

def test_file_changed_during_scanner_not_certified(tmp_path,monkeypatch):
    p=tmp_path/"source.txt";p.write_bytes(b"before")
    def antivirus(*args,**kw):
        p.write_bytes(b"after!")
        return type("Response",(),{"returncode":0})()
    monkeypatch.setattr(s.subprocess,"run",antivirus)
    with pytest.raises(ValueError,match="file_changed"):
        s.scan(p,level="standard",antivirus="local-test-scanner")
