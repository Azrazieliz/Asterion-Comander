"""Asterion Control: opt-in local file safety scanner and reversible quarantine.

No fake antivirus claim. A no-findings verdict only covers inspection that was
actually performed; missing ClamAV is reported, never silently counted as clean.
No network calls or scans of other apps' protected Android directories.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import threading
import time
import uuid
import zipfile
from pathlib import Path
from typing import Callable
from .bridge_worker_lock import worker_process_lock

_CHUNK = 1024 * 1024
_MAX_FILE = 512 * 1024 * 1024
_MAX_ARCHIVE_ITEMS = 2000
_MAX_UNPACKED = 512 * 1024 * 1024
_MAX_RATIO = 200
_RISKY = {".apk",".exe",".dll",".so",".ps1",".bat",".cmd",".sh",".js",
          ".jar",".dex",".scr",".msi",".vbs",".hta",".docm",".xlsm",
          ".pptm",".zip",".7z",".rar",".tar",".gz",".pdf",".epub"}
_EXEC = {".exe",".dll",".so",".ps1",".bat",".cmd",".sh",".js",".jar",
         ".dex",".scr",".msi",".vbs",".hta"}
_LOCK = threading.RLock()
_SAFE_ID = re.compile(r"^[0-9a-f]{32}$")


def _sha256(path: Path, size_cap: int = _MAX_FILE) -> str:
    if path.stat().st_size > size_cap:
        raise ValueError("file_too_large_for_safe_scan")
    digest=hashlib.sha256()
    with path.open("rb") as handle:
        while part:=handle.read(_CHUNK):
            digest.update(part)
    return digest.hexdigest()


def _kind(head: bytes) -> str:
    if head.startswith(b"MZ"): return "pe_executable"
    if head.startswith(b"\x7fELF"): return "elf_binary"
    if head[:4] in (b"PK\x03\x04",b"PK\x05\x06"): return "zip_container"
    if head.startswith(b"%PDF-"): return "pdf"
    if head.startswith(b"#!"): return "script"
    if head.startswith(b"\xd0\xcf\x11\xe0"): return "compound_document"
    if head.startswith(b"Rar!\x1a\x07"): return "rar_container"
    if head.startswith(b"7z\xbc\xaf\x27\x1c"): return "sevenzip_container"
    return "other"


def _zip_findings(path: Path) -> tuple[list[str],dict]:
    findings=[]
    meta={"entries_inspected":0,"declared_uncompressed_bytes":0,"nested_archives":0}
    try:
        with zipfile.ZipFile(path) as archive:
            entries=archive.infolist()
            if len(entries)>_MAX_ARCHIVE_ITEMS:
                return ["archive_entry_count_exceeds_limit"],meta
            total=0
            for entry in entries:
                total+=entry.file_size
                if total>_MAX_UNPACKED:
                    findings.append("archive_expansion_exceeds_limit");break
                ratio=entry.file_size/max(1,entry.compress_size)
                if entry.file_size>8*1024*1024 and ratio>_MAX_RATIO:
                    findings.append("suspicious_compression_ratio");break
                if stat.S_ISLNK(entry.external_attr >> 16):
                    findings.append("archive_contains_symbolic_link")
                if entry.flag_bits & 1:
                    findings.append("encrypted_archive_entry_not_inspected")
                name=entry.filename.replace("\\","/")
                segments=[x for x in name.split("/") if x]
                if name.startswith("/") or ".." in segments or re.match(r"^[a-zA-Z]:",name):
                    findings.append("archive_path_traversal")
                ext=Path(name).suffix.lower()
                if ext in _EXEC:
                    findings.append("archive_contains_executable")
                if ext in {".zip",".7z",".rar",".gz",".tar"}:
                    meta["nested_archives"]+=1
                meta["entries_inspected"]+=1
            meta["declared_uncompressed_bytes"]=total
    except (zipfile.BadZipFile,OSError,ValueError):
        findings.append("invalid_archive")
    return sorted(set(findings)),meta


def scan(path: Path, *, level: str = "auto", antivirus: str | None = None) -> dict:
    """Bounded non-destructive scan. Passing files does not imply virus-free."""
    if level not in {"auto","quick","standard","deep"}:
        raise ValueError("unsupported_scan_level")
    path=Path(path)
    if path.is_symlink():raise ValueError("symbolic_link_not_scannable")
    path=path.resolve(strict=True)
    if not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("regular_file_required")
    ext=path.suffix.lower()
    selected=("deep" if ext in _RISKY else "standard") if level=="auto" else level
    initial=path.stat()
    size=initial.st_size
    if size>_MAX_FILE:
        return {"ok":False,"verdict":"unscannable","reason":"file_too_large",
                "size":size,"max_bytes":_MAX_FILE,"profile":selected}
    started=time.monotonic()
    with path.open("rb") as file: head=file.read(4096)
    kind=_kind(head)
    findings=[]
    if ext in {".txt",".jpg",".jpeg",".png",".mp4",".mp3"} and kind in {
        "pe_executable","elf_binary","script"}:
        findings.append("extension_content_mismatch")
    if kind=="compound_document" or ext in {".docm",".xlsm",".pptm"}:
        findings.append("macro_or_legacy_document_requires_review")
    zip_info=None
    if (selected in {"standard","deep"} and kind=="zip_container") or (
        selected=="deep" and ext in {".apk",".zip",".epub",".jar"}):
        zip_findings,zip_info=_zip_findings(path)
        findings+=zip_findings
    digest=_sha256(path)
    engine_status="not_available"
    malware_name=None
    # A configured, installed local ClamAV can give a signature verdict.
    # No cloud submission; never shell=True or expose a raw file path in JSON.
    candidate=antivirus if antivirus is not None else shutil.which("clamscan")
    if selected!="quick" and candidate:
        try:
            run=subprocess.run([candidate,"--no-summary","--infected",str(path)],
               capture_output=True,text=True,timeout=80,check=False)
            if run.returncode==1:
                engine_status="malware_detected"
                malware_name="clamav_signature_match"
                findings.append("antivirus_signature_match")
            elif run.returncode==0:
                engine_status="scanned_no_signature"
            else:
                engine_status="scanner_error"
        except (OSError,subprocess.TimeoutExpired):
            engine_status="scanner_error"
    final=path.stat()
    if ((initial.st_dev,initial.st_ino,initial.st_size,initial.st_mtime_ns)!=
        (final.st_dev,final.st_ino,final.st_size,final.st_mtime_ns) or _sha256(path)!=digest):
        return {"ok":False,"verdict":"incomplete","reason":"file_changed_during_scan","safe_guarantee":False}
    if "antivirus_signature_match" in findings:
        verdict="malicious"
    elif findings:
        verdict="suspicious"
    elif selected!="quick" and engine_status!="scanned_no_signature":
        verdict="incomplete"
    else:
        verdict="no_known_threat_detected"
    return {
        "ok":True,"profile":selected,"verdict":verdict,
        "file_sha256":digest,"size":size,"detected_type":kind,
        "antivirus":engine_status,"findings":sorted(set(findings)),
        "archive":zip_info,"duration_ms":round((time.monotonic()-started)*1000,2),
        "coverage":"read_only_static_and_optional_local_signature",
        "safe_guarantee":False,
        "cloud_upload":False,
    }


def _vault(root: Path) -> Path:
    vault=root.resolve()/ "quarantine"
    if vault.is_symlink():raise ValueError("unsafe_quarantine_vault")
    vault.mkdir(parents=True,exist_ok=True,mode=0o700)
    if os.name!="nt":vault.chmod(0o700)
    return vault


def _write_meta(path:Path,entry:dict):
    temp=path.with_name(path.name+"."+uuid.uuid4().hex+".pending")
    try:
        with temp.open("x",encoding="utf-8") as handle:
            if os.name!="nt":os.chmod(temp,0o600)
            json.dump(entry,handle,sort_keys=True)
            handle.flush();os.fsync(handle.fileno())
        os.replace(temp,path)
    finally:
        temp.unlink(missing_ok=True)


def _entry(root:Path,item_id:str):
    if not _SAFE_ID.fullmatch(item_id):raise ValueError("invalid_quarantine_id")
    meta=root/(item_id+".json");blob=root/(item_id+".blob")
    if meta.is_symlink() or blob.is_symlink():raise ValueError("unsafe_quarantine_record")
    data=json.loads(meta.read_text("utf-8"))
    if data.get("id")!=item_id or not re.fullmatch(r"[0-9a-f]{64}",data.get("sha256","")):
        raise ValueError("quarantine_metadata_invalid")
    return meta,blob,data


def quarantine(source:Path,vault_root:Path,expected_sha256:str)->dict:
    """Owner-approved same-filesystem atomic move with durable pre-move receipt."""
    source=Path(source)
    if source.is_symlink():raise ValueError("invalid_source")
    source=source.resolve(strict=True)
    if not re.fullmatch(r"[0-9a-f]{64}",expected_sha256):raise ValueError("expected_sha256_required")
    root=_vault(Path(vault_root))
    if not source.is_file() or source.is_relative_to(root):raise ValueError("invalid_source")
    with _LOCK,worker_process_lock(root/".quarantine.lock"):
        if source.stat().st_nlink!=1:raise ValueError("source_has_multiple_hardlinks")
        if _sha256(source)!=expected_sha256:raise ValueError("file_changed_before_quarantine")
        if source.stat().st_dev!=root.stat().st_dev:raise ValueError("quarantine_requires_same_filesystem")
        token=uuid.uuid4().hex
        destination=root/(token+".blob");meta=root/(token+".json")
        entry={"id":token,"source":str(source),"sha256":expected_sha256,"size":source.stat().st_size,
            "created_at_ms":time.time_ns()//1000000,"state":"move_pending"}
        _write_meta(meta,entry)
        try:
            # Atomic no-clobber publication of the vault copy. Retain the
            # pending receipt if interruption occurs before unlinking source.
            os.link(source,destination,follow_symlinks=False)
            if not os.path.samefile(source,destination) or _sha256(destination)!=expected_sha256:
                raise ValueError("file_changed_during_quarantine")
            source.unlink()
        except BaseException:
            # Keep durable pending receipt; never remove potential evidence.
            raise
        if _sha256(destination)!=expected_sha256:
            entry["state"]="integrity_review";_write_meta(meta,entry)
            raise ValueError("file_changed_during_quarantine")
        entry["state"]="quarantined";_write_meta(meta,entry)
    return {"ok":True,"id":token,"sha256":expected_sha256,"state":"quarantined","reversible":True}


def original_destination(item_id:str,vault_root:Path)->Path:
    _,_,entry=_entry(_vault(Path(vault_root)),item_id)
    return Path(entry["source"])


def restore(item_id:str,vault_root:Path,approved_destination:Path|None=None)->dict:
    """No-clobber restore. Retain the receipt even after successful restoration."""
    root=_vault(Path(vault_root))
    with _LOCK,worker_process_lock(root/".quarantine.lock"):
        meta,blob,entry=_entry(root,item_id)
        original=Path(entry["source"])
        dest=original if approved_destination is None else Path(approved_destination)
        if dest.is_symlink() or dest.resolve().is_relative_to(root):raise ValueError("unsafe_restore_destination")
        dest=dest.resolve()
        if entry.get("state")=="restored":
            if dest.is_file() and _sha256(dest)==entry["sha256"]:
                if blob.exists():
                    if not os.path.samefile(blob,dest):raise ValueError("restored_blob_identity_changed")
                    blob.unlink()
                return {"ok":True,"id":item_id,"state":"restored","sha256":entry["sha256"]}
            raise ValueError("restored_destination_changed")
        if not dest.parent.is_dir():raise FileNotFoundError("destination_parent_missing")
        if not blob.is_file() or _sha256(blob)!=entry["sha256"]:raise ValueError("quarantine_integrity_failed")
        # Hard-link creation fails atomically if destination exists. No silent
        # overwrite, cross-volume copy, or deletion of original bytes on failure.
        if entry.get("state") in {"restore_pending","move_pending"} and dest.exists():
            if not os.path.samefile(blob,dest):raise FileExistsError("destination_already_exists")
        else:
            if dest.exists():raise FileExistsError("destination_already_exists")
            entry["state"]="restore_pending";_write_meta(meta,entry)
            os.link(blob,dest)
        if not os.path.samefile(blob,dest) or _sha256(dest)!=entry["sha256"]:
            raise ValueError("restore_integrity_failed")
        entry["state"]="restored";_write_meta(meta,entry)
        # Only the duplicate vault link is removed; destination is retained.
        blob.unlink()
    return {"ok":True,"id":item_id,"state":"restored","sha256":entry["sha256"]}


def inventory(vault_root:Path,limit:int=50)->dict:
    if not 1<=limit<=100:raise ValueError("invalid_limit")
    root=_vault(Path(vault_root));rows=[]
    for file in sorted(root.glob("*.json"),key=lambda p:p.stat().st_mtime,reverse=True)[:limit]:
        try:
            _,blob,entry=_entry(root,file.stem)
            state=entry.get("state","quarantined")
            if state=="move_pending":
                original=Path(entry["source"])
                state=("move_interrupted_source_retained" if blob.is_file() and original.exists() and os.path.samefile(blob,original)
                       else "move_receipt_pending" if blob.is_file() else "move_not_observed")
            if state=="quarantined" and not blob.is_file():state="missing_blob_review"
            rows.append({"id":entry["id"],"sha256":entry["sha256"],"size":entry["size"],
                "created_at_ms":entry["created_at_ms"],"state":state})
        except (ValueError,KeyError,OSError):continue
    return {"ok":True,"items":rows,"count":len(rows)}
