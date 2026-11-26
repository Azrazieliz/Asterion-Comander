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
from .bridge_worker_lock import worker_process_lock, WorkerAlreadyRunning

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
    initial=path.lstat()
    if not stat.S_ISREG(initial.st_mode) or initial.st_size>size_cap:
        raise ValueError("regular_bounded_file_required")
    digest=hashlib.sha256()
    flags=os.O_RDONLY|getattr(os,"O_NOFOLLOW",0)|getattr(os,"O_BINARY",0)
    fd=os.open(path,flags)
    with os.fdopen(fd,"rb") as handle:
        opened=os.fstat(handle.fileno())
        if _fingerprint(opened)!=_fingerprint(initial):raise ValueError("file_changed_before_scan")
        total=0
        while part:=handle.read(_CHUNK):
            total+=len(part)
            if total>size_cap:raise ValueError("file_grew_during_scan")
            digest.update(part)
        if _fingerprint(os.fstat(handle.fileno()))!=_fingerprint(initial):
            raise ValueError("file_changed_during_scan")
    if _fingerprint(path.lstat())!=_fingerprint(initial):
        raise ValueError("file_changed_during_scan")
    return digest.hexdigest()


def _fingerprint(info):
    return (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns)


def _same_file(a: Path,b: Path) -> bool:
    try:return os.path.samestat(a.lstat(),b.lstat())
    except OSError:return False


def _regular(path: Path) -> Path:
    path=Path(path).absolute()
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or getattr(info,"st_file_attributes",0)&getattr(stat,"FILE_ATTRIBUTE_REPARSE_POINT",0):
        raise ValueError("regular_non_link_file_required")
    return path.resolve(strict=True)


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
            seen=set()
            for entry in entries:
                total+=entry.file_size
                if total>_MAX_UNPACKED:
                    findings.append("archive_expansion_exceeds_limit");break
                ratio=entry.file_size/max(1,entry.compress_size)
                if entry.file_size>8*1024*1024 and ratio>_MAX_RATIO:
                    findings.append("suspicious_compression_ratio");break
                name=entry.filename.replace("\\","/")
                segments=[x for x in name.split("/") if x]
                if name.startswith("/") or ".." in segments or re.match(r"^[a-zA-Z]:",name):
                    findings.append("archive_path_traversal")
                normalized="/".join(segments).casefold()
                if normalized in seen:findings.append("archive_duplicate_path")
                seen.add(normalized)
                if stat.S_ISLNK(entry.external_attr>>16):findings.append("archive_symlink")
                if entry.flag_bits&1:findings.append("archive_encrypted_entry_not_inspected")
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
    path=_regular(path)
    initial=_fingerprint(path.lstat())
    ext=path.suffix.lower()
    selected=("deep" if ext in _RISKY else "standard") if level=="auto" else level
    size=path.stat().st_size
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
    if _fingerprint(path.lstat())!=initial or _sha256(path)!=digest:
        return {"ok":False,"verdict":"incomplete","reason":"file_changed_during_scan","safe_guarantee":False,"cloud_upload":False}
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
    vault=root.resolve()/"quarantine"
    vault.mkdir(parents=True,exist_ok=True)
    if vault.is_symlink() or not vault.is_dir():raise ValueError("unsafe_quarantine_directory")
    return vault


def _metadata(path: Path, entry: dict) -> None:
    with path.open("x",encoding="utf-8") as handle:
        json.dump(entry,handle,sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())


def _read_entry(meta: Path, item_id: str) -> dict:
    if meta.is_symlink():raise ValueError("unsafe_quarantine_metadata")
    entry=json.loads(meta.read_text("utf-8"))
    if entry.get("id")!=item_id or not re.fullmatch(r"[0-9a-f]{64}",str(entry.get("sha256",""))):
        raise ValueError("quarantine_metadata_invalid")
    if not isinstance(entry.get("source"),str) or not Path(entry["source"]).is_absolute():
        raise ValueError("quarantine_source_invalid")
    return entry


def quarantine(source: Path, vault_root: Path, expected_sha256: str) -> dict:
    """Hash-bound no-overwrite move. Hard-link staging stays on the same volume.
    A crash between link and unlink preserves both names, not an unknown deletion.
    """
    source=_regular(source)
    if not re.fullmatch(r"[0-9a-f]{64}",expected_sha256):
        raise ValueError("expected_sha256_required")
    root=_vault(Path(vault_root))
    if source.is_relative_to(root):raise ValueError("already_quarantined")
    with _LOCK,worker_process_lock(root/".vault.lock"):
        info=source.lstat()
        if info.st_nlink!=1:raise ValueError("multiple_hardlinks_require_review")
        if _sha256(source)!=expected_sha256:raise ValueError("file_changed_before_quarantine")
        token=uuid.uuid4().hex;destination=root/(token+".blob");meta=root/(token+".json")
        _metadata(meta,{"id":token,"source":str(source),"sha256":expected_sha256,
                        "size":info.st_size,"created_at_ms":time.time_ns()//1000000})
        linked=False
        try:
            # Unlike replace(), link() fails if any target already exists.
            os.link(source,destination,follow_symlinks=False);linked=True
            if not _same_file(source,destination) or _sha256(destination)!=expected_sha256:
                raise ValueError("quarantine_source_changed")
            source.unlink()
        except BaseException:
            # If we already linked the bytes, retain the receipt and blob for
            # explicit recovery; never assume the original name is safe to delete.
            if not linked:meta.unlink(missing_ok=True)
            raise
        if _sha256(destination)!=expected_sha256:raise ValueError("quarantine_integrity_failed")
    return {"ok":True,"id":token,"sha256":expected_sha256,"state":"quarantined","reversible":True}


def restore(item_id: str, vault_root: Path, approved_destination: Path | None = None,
            authorize: Callable[[Path],Path] | None = None) -> dict:
    """Restore only the original/explicitly approved path; never replace any file."""
    if not _SAFE_ID.fullmatch(item_id):raise ValueError("invalid_quarantine_id")
    root=_vault(Path(vault_root));meta=root/(item_id+".json");blob=root/(item_id+".blob")
    with _LOCK,worker_process_lock(root/".vault.lock"):
        entry=_read_entry(meta,item_id)
        dest=Path(entry["source"]) if approved_destination is None else Path(approved_destination).absolute()
        if authorize is not None and authorize(dest)!=dest:
            raise ValueError("restore_scope_changed")
        if dest.is_relative_to(root) or not dest.parent.is_dir() or dest.parent.resolve()!=dest.parent:
            raise ValueError("unsafe_restore_destination")
        if not blob.exists():
            # Prior restore may have completed before metadata cleanup.
            if dest.is_file() and not dest.is_symlink() and _sha256(dest)==entry["sha256"]:
                meta.unlink()
                return {"ok":True,"id":item_id,"state":"restored","sha256":entry["sha256"],"reconciled":True}
            raise FileNotFoundError("quarantine_blob_missing")
        if _regular(blob)!=blob or _sha256(blob)!=entry["sha256"]:
            raise ValueError("quarantine_integrity_failed")
        if os.path.lexists(dest):
            # Recover a crash in either move direction only when it is the exact
            # same underlying file and digest. An unrelated file is never touched.
            if not _same_file(blob,dest):raise FileExistsError("destination_already_exists")
        else:os.link(blob,dest,follow_symlinks=False)
        if not _same_file(blob,dest) or _sha256(dest)!=entry["sha256"]:
            raise ValueError("restore_integrity_failed")
        blob.unlink()
        meta.unlink()
    return {"ok":True,"id":item_id,"state":"restored","sha256":entry["sha256"]}


def inventory(vault_root: Path, limit: int = 50) -> dict:
    if not 1<=limit<=100:raise ValueError("invalid_limit")
    root=_vault(Path(vault_root));rows=[]
    for file in sorted(root.glob("*.json"),key=lambda p:p.stat().st_mtime,reverse=True)[:limit]:
        try:
            if not _SAFE_ID.fullmatch(file.stem):continue
            entry=_read_entry(file,file.stem)
            blob=root/(file.stem+".blob");source=Path(entry["source"])
            state=("quarantine_or_restore_interrupted" if _same_file(blob,source) else
                   "quarantined" if blob.is_file() and not blob.is_symlink() else "receipt_requires_reconciliation")
            rows.append({"id":entry["id"],"sha256":entry["sha256"],"size":entry["size"],
                         "created_at_ms":entry["created_at_ms"],"state":state})
        except (ValueError,KeyError,OSError):continue
    return {"ok":True,"items":rows,"count":len(rows)}
