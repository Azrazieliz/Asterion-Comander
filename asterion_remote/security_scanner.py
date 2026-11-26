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
import contextlib
import subprocess
import threading
import time
import uuid
import zipfile
from pathlib import Path
from typing import Callable

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


def _reparse(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) &
            getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def _regular(path: Path, *, unique=False):
    """Refuse symlinks/reparse points, including directory components."""
    path=Path(os.path.abspath(path))
    for component in (path, *path.parents):
        info=component.lstat()
        if _reparse(info):
            raise ValueError("symbolic_or_reparse_path_refused")
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or (unique and info.st_nlink!=1):
        raise ValueError("regular_unlinked_file_required")
    return info


@contextlib.contextmanager
def _stable_open(path: Path):
    before=_regular(path)
    flags=os.O_RDONLY|getattr(os,"O_BINARY",0)|getattr(os,"O_NOFOLLOW",0)
    fd=os.open(path,flags)
    with os.fdopen(fd,"rb") as handle:
        if _identity(os.fstat(handle.fileno()))!=_identity(before):
            raise ValueError("file_changed_before_scan")
        yield handle
        if _identity(os.fstat(handle.fileno()))!=_identity(before) or _identity(_regular(path))!=_identity(before):
            raise ValueError("file_changed_during_scan")


def _sha256(path: Path, size_cap: int = _MAX_FILE) -> str:
    if _regular(path).st_size > size_cap:
        raise ValueError("file_too_large_for_safe_scan")
    digest=hashlib.sha256();read=0
    with _stable_open(path) as handle:
        while part:=handle.read(_CHUNK):
            read+=len(part)
            if read>size_cap:raise ValueError("file_grew_during_scan")
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


def _zip_findings(path: Path, deep: bool=False) -> tuple[list[str],dict]:
    findings=[]
    meta={"entries_inspected":0,"declared_uncompressed_bytes":0,"nested_archives":0,"content_bytes_verified":0,"encrypted_entries":0,"deep_content_complete":False}
    seen=set()
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
                name=entry.filename.replace("\\","/")
                segments=[x for x in name.split("/") if x]
                if name.startswith("/") or ".." in segments or re.match(r"^[a-zA-Z]:",name):
                    findings.append("archive_path_traversal")
                normalized="/".join(s.rstrip(" .").casefold() for s in segments)
                if normalized in seen:findings.append("archive_duplicate_or_alias_path")
                seen.add(normalized)
                if any(":" in s or s.rstrip(" .")=="" for s in segments):findings.append("archive_ambiguous_path")
                unix_mode=(entry.external_attr>>16)&0xffff
                if stat.S_ISLNK(unix_mode):findings.append("archive_contains_symlink")
                if entry.flag_bits&1:
                    meta["encrypted_entries"]+=1;findings.append("archive_encrypted_entry_not_inspected")
                if name.lower().endswith("vbaproject.bin"):findings.append("archive_contains_macro_project")
                ext=Path(name).suffix.lower()
                if ext in _EXEC:
                    findings.append("archive_contains_executable")
                if ext in {".zip",".7z",".rar",".gz",".tar"}:
                    meta["nested_archives"]+=1
                if deep and not entry.is_dir() and not entry.flag_bits&1 and not stat.S_ISLNK(unix_mode):
                    # No extraction or execution: read bounded bytes to verify CRC.
                    count=0
                    with archive.open(entry) as member:
                        while part:=member.read(_CHUNK):
                            count+=len(part);meta["content_bytes_verified"]+=len(part)
                            if count>entry.file_size or meta["content_bytes_verified"]>_MAX_UNPACKED:
                                raise ValueError("archive_actual_expansion_exceeds_limit")
                    if count!=entry.file_size:findings.append("archive_entry_length_mismatch")
                meta["entries_inspected"]+=1
            meta["declared_uncompressed_bytes"]=total
            meta["deep_content_complete"]=deep and meta["entries_inspected"]==len(entries) and meta["encrypted_entries"]==0 and not meta["nested_archives"] and not findings
    except (zipfile.BadZipFile,OSError,ValueError,RuntimeError,NotImplementedError):
        findings.append("invalid_archive")
    return sorted(set(findings)),meta


def scan(path: Path, *, level: str = "auto", antivirus: str | None = None) -> dict:
    """Bounded non-destructive scan. Passing files does not imply virus-free."""
    if level not in {"auto","quick","standard","deep"}:
        raise ValueError("unsupported_scan_level")
    path=Path(os.path.abspath(path))
    initial=_regular(path)
    ext=path.suffix.lower()
    selected=("deep" if ext in _RISKY else "standard") if level=="auto" else level
    size=initial.st_size
    if size>_MAX_FILE:
        return {"ok":False,"verdict":"unscannable","reason":"file_too_large",
                "size":size,"max_bytes":_MAX_FILE,"profile":selected}
    started=time.monotonic()
    with _stable_open(path) as file: head=file.read(4096)
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
        zip_findings,zip_info=_zip_findings(path,deep=selected=="deep")
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
    # Never bind a signature result to bytes that were replaced during inspection.
    if _identity(_regular(path))!=_identity(initial) or _sha256(path)!=digest:
        raise ValueError("file_changed_during_scan")
    if "antivirus_signature_match" in findings:
        verdict="malicious"
    elif findings:
        verdict="suspicious"
    elif selected!="quick" and (engine_status!="scanned_no_signature" or
            (zip_info is not None and (zip_info["nested_archives"] or zip_info["encrypted_entries"])) or
            (kind in {"rar_container","sevenzip_container"})) :
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
    vault=Path(os.path.abspath(root))/"quarantine"
    vault.mkdir(parents=True,exist_ok=True)
    for component in (vault,*vault.parents):
        if _reparse(component.lstat()):raise ValueError("unsafe_quarantine_directory")
    return vault


def _write_metadata(path: Path, data: dict):
    # Exclusive durable create: a partial journal is never interpreted as a
    # completed quarantine. The original source is untouched until fsync.
    with path.open("x", encoding="utf-8") as handle:
        json.dump(data,handle,sort_keys=True)
        handle.flush();os.fsync(handle.fileno())


def _sync_directory(path: Path):
    if os.name!="nt":
        fd=os.open(path,os.O_RDONLY|getattr(os,"O_DIRECTORY",0))
        try:os.fsync(fd)
        finally:os.close(fd)


def _rename_noreplace(source: Path, destination: Path):
    # Windows rename is no-replace. Linux renameat2 provides the same
    # atomic contract; never fall back to a check-then-overwrite sequence.
    if os.name=="nt":
        os.rename(source,destination)
        return
    import ctypes
    import errno
    libc=ctypes.CDLL(None,use_errno=True)
    rename=getattr(libc,"renameat2",None)
    if rename is None:raise OSError(errno.ENOTSUP,"atomic no-replace move unavailable")
    rename.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
    rename.restype=ctypes.c_int
    if rename(-100,os.fsencode(source),-100,os.fsencode(destination),1)!=0:
        code=ctypes.get_errno()
        raise OSError(code,os.strerror(code))


def quarantine(source: Path, vault_root: Path, expected_sha256: str) -> dict:
    """Hash-bound same-volume quarantine with non-overwriting durable staging."""
    source=Path(os.path.abspath(source))
    if not re.fullmatch(r"[0-9a-f]{64}",expected_sha256):
        raise ValueError("expected_sha256_required")
    root=_vault(Path(vault_root))
    if source.is_relative_to(root):raise ValueError("already_quarantined")
    with _LOCK:
        original=_regular(source,unique=True)
        if _sha256(source)!=expected_sha256:raise ValueError("file_changed_before_quarantine")
        if _identity(_regular(source,unique=True))!=_identity(original):
            raise ValueError("file_changed_before_quarantine")
        token=uuid.uuid4().hex;destination=root/(token+".blob");meta=root/(token+".json")
        _write_metadata(meta,{"id":token,"source":str(source),"sha256":expected_sha256,
                              "size":original.st_size,"created_at_ms":time.time_ns()//1000000})
        _sync_directory(root)
        try:
            _rename_noreplace(source,destination)
        except BaseException:
            meta.unlink(missing_ok=True);raise
        _sync_directory(root);_sync_directory(source.parent)
        # If a concurrent writer changed the file, do not delete any bytes.
        # Retain the journal and moved content for explicit recovery.
        if _identity(_regular(destination))!=_identity(original) or _sha256(destination)!=expected_sha256:
            raise ValueError("quarantine_staged_integrity_failed")
    return {"ok":True,"id":token,"sha256":expected_sha256,
            "state":"quarantined","reversible":True}


def restore(item_id: str, vault_root: Path, approved_destination: Path | None = None,
            authorize: Callable[[Path],Path] | None = None) -> dict:
    """No-clobber restore with restart reconciliation of interrupted moves."""
    if not _SAFE_ID.fullmatch(item_id):raise ValueError("invalid_quarantine_id")
    root=_vault(Path(vault_root));meta=root/(item_id+".json");blob=root/(item_id+".blob")
    with _LOCK:
        _regular(meta)
        entry=json.loads(meta.read_text("utf-8"))
        if entry.get("id")!=item_id or not re.fullmatch(r"[0-9a-f]{64}",entry.get("sha256","")):
            raise ValueError("invalid_quarantine_metadata")
        dest=Path(os.path.abspath(entry["source"] if approved_destination is None else approved_destination))
        if authorize is not None and authorize(dest)!=dest:
            raise ValueError("restore_destination_changed")
        if dest.is_relative_to(root):raise ValueError("restore_destination_inside_vault")
        for parent in (dest.parent,*dest.parent.parents):
            if _reparse(parent.lstat()):raise ValueError("unsafe_restore_parent")
        if not blob.exists():
            # A crash after blob removal but before metadata cleanup.
            if dest.exists() and _sha256(dest)==entry["sha256"]:
                meta.unlink();_sync_directory(root)
                return {"ok":True,"id":item_id,"state":"restored","sha256":entry["sha256"],"reconciled":True}
            raise FileNotFoundError("quarantine_blob_missing")
        blob_info=_regular(blob)
        if _sha256(blob)!=entry["sha256"]:raise ValueError("quarantine_integrity_failed")
        if dest.exists() or dest.is_symlink():
            raise FileExistsError("destination_already_exists")
        _rename_noreplace(blob,dest)
        _sync_directory(dest.parent);_sync_directory(root)
        if _identity(_regular(dest))!=_identity(blob_info) or _sha256(dest)!=entry["sha256"]:
            raise ValueError("restore_staged_integrity_failed")
        meta.unlink();_sync_directory(root)
    return {"ok":True,"id":item_id,"state":"restored","sha256":entry["sha256"]}


def inventory(vault_root: Path, limit: int = 50) -> dict:
    if not 1<=limit<=100: raise ValueError("invalid_limit")
    root=_vault(Path(vault_root))
    rows=[]
    for file in sorted(root.glob("*.json"),key=lambda p:p.stat().st_mtime,reverse=True)[:limit]:
        try:
            entry=json.loads(file.read_text("utf-8"))
            if not _SAFE_ID.fullmatch(entry.get("id","")):continue
            blob=root/(entry["id"]+".blob");source=Path(entry["source"])
            state="quarantined" if blob.is_file() and not source.exists() else "recovery_required"
            rows.append({"id":entry["id"],"sha256":entry["sha256"],
                         "size":entry["size"],"created_at_ms":entry["created_at_ms"],"state":state})
        except (ValueError,KeyError,OSError):continue
    return {"ok":True,"items":rows,"count":len(rows)}
