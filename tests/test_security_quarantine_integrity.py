import hashlib
import os
import stat
import zipfile
import pytest
from asterion_remote import security_scanner as s

def digest(data):return hashlib.sha256(data).hexdigest()

def test_real_quarantine_and_restore_without_clobber(tmp_path):
    source=tmp_path/"test.txt";source.write_bytes(b"fixture")
    vault=tmp_path/"vault"
    q=s.quarantine(source,vault,digest(b"fixture"))
    assert not source.exists()
    assert s.inventory(vault)["items"][0]["state"]=="quarantined"
    source.write_bytes(b"other")
    with pytest.raises(FileExistsError):s.restore(q["id"],vault)
    assert source.read_bytes()==b"other"
    source.unlink()
    assert s.restore(q["id"],vault)["state"]=="restored"
    assert source.read_bytes()==b"fixture"
    assert s.inventory(vault)["count"]==0

def test_interrupted_quarantine_link_is_recoverable(tmp_path,monkeypatch):
    source=tmp_path/"test.txt";source.write_bytes(b"fixture")
    original=s.Path.unlink
    def fail(p,*a,**kw):
        if p==source:raise OSError("injected crash before original unlink")
        return original(p,*a,**kw)
    monkeypatch.setattr(s.Path,"unlink",fail)
    vault=tmp_path/"vault"
    with pytest.raises(OSError):s.quarantine(source,vault,digest(b"fixture"))
    row=s.inventory(vault)["items"][0]
    assert row["state"]=="quarantine_or_restore_interrupted"
    monkeypatch.setattr(s.Path,"unlink",original)
    s.restore(row["id"],vault)
    assert source.read_bytes()==b"fixture"

def test_restore_scope_and_tamper_checks(tmp_path):
    source=tmp_path/"test.txt";source.write_bytes(b"fixture")
    vault=tmp_path/"vault"
    q=s.quarantine(source,vault,digest(b"fixture"))
    with pytest.raises(ValueError,match="scope"):s.restore(q["id"],vault,authorize=lambda p:tmp_path/"wrong")
    blob=vault/"quarantine"/(q["id"]+".blob")
    blob.write_bytes(b"tampered")
    with pytest.raises(ValueError,match="integrity"):s.restore(q["id"],vault)
    assert not source.exists()

def test_symlinks_and_multiple_links_rejected(tmp_path):
    source=tmp_path/"test.txt";source.write_bytes(b"fixture")
    link=tmp_path/"link";link.symlink_to(source)
    with pytest.raises(ValueError):s.scan(link)
    hard=tmp_path/"hard";os.link(source,hard)
    with pytest.raises(ValueError,match="multiple_hardlinks"):s.quarantine(source,tmp_path/"vault",digest(b"fixture"))
    assert source.exists() and hard.exists()

def test_archive_links_and_duplicate_names_are_reported(tmp_path):
    p=tmp_path/"test.zip"
    with zipfile.ZipFile(p,"w") as archive:
        archive.writestr("a.txt","one")
        archive.writestr("A.TXT","two")
        link=zipfile.ZipInfo("link");link.create_system=3;link.external_attr=(stat.S_IFLNK|0o777)<<16
        archive.writestr(link,"a.txt")
        archive.writestr("../outside.txt","bad")
    row=s.scan(p,level="deep",antivirus="")
    assert row["verdict"]=="suspicious"
    assert {"archive_duplicate_path","archive_symlink","archive_path_traversal"}<=set(row["findings"])
