import hashlib
import os
import zipfile
import stat
import pytest
from asterion_remote import security_scanner as scanner, browser_crawler

def digest(data):return hashlib.sha256(data).hexdigest()

def test_quarantine_roundtrip_and_persistent_receipt(tmp_path):
    source=tmp_path/"sample.txt";source.write_bytes(b"fixture")
    vault=tmp_path/"vault"
    q=scanner.quarantine(source,vault,digest(b"fixture"))
    assert not source.exists()
    assert scanner.inventory(vault)["items"][0]["state"]=="quarantined"
    source.write_bytes(b"new")
    with pytest.raises(FileExistsError):scanner.restore(q["id"],vault)
    assert source.read_bytes()==b"new"
    source.unlink()
    assert scanner.restore(q["id"],vault)["state"]=="restored"
    assert source.read_bytes()==b"fixture"
    assert scanner.restore(q["id"],vault)["state"]=="restored"
    assert scanner.inventory(vault)["items"][0]["state"]=="restored"

def test_interrupted_restore_reconciles_same_inode(tmp_path,monkeypatch):
    source=tmp_path/"file";source.write_bytes(b"sample")
    vault=tmp_path/"vault";q=scanner.quarantine(source,vault,digest(b"sample"))
    original=scanner._write_meta
    def crash(path,entry):
        if entry["state"]=="restored":raise OSError("fixture process interruption")
        original(path,entry)
    monkeypatch.setattr(scanner,"_write_meta",crash)
    with pytest.raises(OSError):scanner.restore(q["id"],vault)
    assert source.read_bytes()==b"sample"
    monkeypatch.setattr(scanner,"_write_meta",original)
    assert scanner.restore(q["id"],vault)["state"]=="restored"

def test_changed_source_and_archive_symlink(tmp_path):
    path=tmp_path/"sample.zip"
    with zipfile.ZipFile(path,"w") as archive:
        entry=zipfile.ZipInfo("link");entry.create_system=3
        entry.external_attr=(stat.S_IFLNK|0o777)<<16
        archive.writestr(entry,"../outside")
    report=scanner.scan(path,level="deep",antivirus="")
    assert "archive_contains_symbolic_link" in report["findings"]
    with pytest.raises(ValueError):scanner.quarantine(path,tmp_path/"vault","0"*64)
    assert path.exists()

def test_onion_crawler_rejected_before_dns(monkeypatch):
    monkeypatch.setattr(browser_crawler.socket,"getaddrinfo",lambda *a,**k:pytest.fail("onion DNS leak"))
    with pytest.raises(browser_crawler.HTTPException) as error:
        browser_crawler.validated_public_https("https://"+"a"*56+".onion/")
    assert error.value.status_code==403
