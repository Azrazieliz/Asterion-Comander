"""Automatic *scoped* file scanning for owner-authorized Windows drop folders.

Reuses existing signature/heuristic engine, avoiding a second antivirus. On
files stable for >=3 seconds, Standard scan is automatic for ordinary files
and Deep for executables, APKs, archives and macro-capable documents.
Only confirmed signature matches are automatically quarantined; heuristic
alerts need owner review to prevent silently deleting important documents.

Nothing scans other Android apps' private storage. Disabled at startup unless
the owner explicitly configures both an allowed folder and enable flag.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sqlite3
import threading
import time
from typing import Iterable

from . import security_scanner

_LOCK=threading.RLock()
_STOP=threading.Event()
_SIGNAL=threading.Event()
_WORKER:threading.Thread|None=None
_STABLE_S=3
_MAX_PER_PASS=60


def _root()->Path:
    base=Path(os.getenv("ASTERION_SECURITY_GUARDIAN_STATE",str(
        Path(os.getenv("LOCALAPPDATA",str(Path.home())))/
        "AsterionControl"/"file-guardian"))).expanduser().resolve()
    base.mkdir(parents=True,exist_ok=True)
    return base


def _db()->sqlite3.Connection:
    db=sqlite3.connect(str(_root()/"guardian.sqlite3"),
                       isolation_level=None,timeout=6)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=FULL")
    db.execute("""CREATE TABLE IF NOT EXISTS scanned(
      path_digest TEXT PRIMARY KEY,
      content_sha256 TEXT NOT NULL,
      size_bytes INTEGER NOT NULL,
      mtime_ns INTEGER NOT NULL,
      verdict TEXT NOT NULL,
      engine TEXT NOT NULL,
      last_scan_ms INTEGER NOT NULL
    )""")
    return db


def _paths()->tuple[Path,...]:
    if os.getenv("ASTERION_SECURITY_GUARDIAN_ENABLED","0")!="1":
        raise RuntimeError("owner_security_guardian_disabled")
    raw=os.getenv("ASTERION_SECURITY_WATCH_ROOTS","")
    if not raw or len(raw)>8192:
        raise RuntimeError("owner_authorized_watch_roots_not_configured")
    from .app import ROOT,EXTRA_ROOTS
    allowed=(ROOT,*EXTRA_ROOTS)
    result=[]
    for item in raw.split(os.pathsep):
        if not item.strip():continue
        folder=Path(item).expanduser()
        if not folder.is_absolute() or not folder.is_dir() or folder.is_symlink():
            raise ValueError("watch_root_must_be_real_authorized_directory")
        folder=folder.resolve(strict=True)
        if not any(folder.is_relative_to(known) for known in allowed):
            raise PermissionError("watch_root_outside_existing_Control_roots")
        if folder==_root() or _root().is_relative_to(folder):
            raise PermissionError("watch_root_cannot_include_guardian_state")
        if folder not in result:result.append(folder)
    if not 1<=len(result)<=12:
        raise ValueError("invalid_number_of_watch_roots")
    return tuple(result)


def _candidates(roots:Iterable[Path]):
    for root in roots:
        count=0
        # A short bounded recursive walk; no symlinks and no archived data
        # expansion. Original files are not modified during normal scanning.
        for folder,subdirs,files in os.walk(root,followlinks=False):
            base=Path(folder)
            depth=len(base.relative_to(root).parts)
            if depth>=3:subdirs[:]=[]
            else:
                subdirs[:]=[x for x in subdirs[:40] if not (
                    base/x).is_symlink() and not x.startswith(".")]
            for name in files[:300]:
                if name.startswith("."):continue
                file=base/name
                try:
                    if file.is_file() and not file.is_symlink():
                        yield file
                        count+=1
                except OSError:continue
                if count>=_MAX_PER_PASS:break
            if count>=_MAX_PER_PASS:break


def scan_once(*,stable_age_s:int=_STABLE_S)->dict:
    if not isinstance(stable_age_s,int) or not 0<=stable_age_s<=60:
        raise ValueError("invalid_file_stability_delay")
    roots=_paths()
    now=time.time()
    checked=0
    skipped=0
    review=0
    quarantined=0
    failures=0
    inventory=[]
    with _LOCK:
        db=_db()
        try:
            for file in _candidates(roots):
                if checked>=_MAX_PER_PASS:break
                try:
                    st=file.stat()
                    if now-st.st_mtime<stable_age_s:
                        skipped+=1;continue
                    if st.st_size>security_scanner._MAX_FILE:
                        skipped+=1;continue
                    identity=hashlib.sha256(str(file).encode()).hexdigest()
                    old=db.execute(
                      "SELECT size_bytes,mtime_ns FROM scanned WHERE path_digest=?",
                      (identity,)).fetchone()
                    if old and old==(st.st_size,st.st_mtime_ns):
                        skipped+=1;continue
                    verdict=security_scanner.scan(file,level="auto")
                    if not verdict["ok"]:
                        skipped+=1;continue
                    checked+=1
                    status=verdict["verdict"]
                    action="observed"
                    if status=="malicious":
                        try:
                            item=security_scanner.quarantine(
                                file,_root(),verdict["file_sha256"])
                            quarantined+=1
                            action="quarantined"
                        except (OSError,ValueError):
                            action="quarantine_failed";failures+=1
                    elif status in {"suspicious","incomplete","unscannable"}:
                        review+=1;action="owner_review_required"
                    inventory.append({"sha256":verdict["file_sha256"],
                                      "verdict":status,"action":action})
                    db.execute("""INSERT INTO scanned
                       (path_digest,content_sha256,size_bytes,mtime_ns,
                        verdict,engine,last_scan_ms)
                       VALUES(?,?,?,?,?,?,?)
                       ON CONFLICT(path_digest) DO UPDATE SET
                       content_sha256=excluded.content_sha256,
                       size_bytes=excluded.size_bytes,
                       mtime_ns=excluded.mtime_ns,
                       verdict=excluded.verdict,
                       engine=excluded.engine,
                       last_scan_ms=excluded.last_scan_ms""",
                       (identity,verdict["file_sha256"],st.st_size,
                        st.st_mtime_ns,status,verdict["antivirus"],
                        time.time_ns()//1000000))
                except (OSError,ValueError,RuntimeError):
                    failures+=1
        finally:db.close()
    return {"ok":True,"files_inspected":checked,
            "unchanged_or_incomplete_files_skipped":skipped,
            "owner_review_needed":review,"auto_quarantined":quarantined,
            "file_errors":failures,"outcomes":inventory,
            "automatic_quarantine_requires_signature_match":True,
            "android_private_apps_scanned":False,
            "full_antivirus_guarantee":False}


def status()->dict:
    ready=os.getenv("ASTERION_SECURITY_GUARDIAN_ENABLED","0")=="1"
    try:
        roots=len(_paths()) if ready else 0
        error=""
    except Exception as exc:
        roots=0;error=type(exc).__name__
    return {"enabled":ready,"configured_roots":roots,
            "worker_running":bool(_WORKER and _WORKER.is_alive()),
            "last_configuration_error":error,
            "automatic_quarantine_only_on_signature_match":True,
            "mobile_private_data_available":False}


def _loop():
    while not _STOP.is_set():
        try:scan_once()
        except Exception:pass
        try:interval=max(20,min(3600,int(os.getenv(
            "ASTERION_SECURITY_SCAN_INTERVAL_S","90"))))
        except ValueError:interval=90
        _STOP.wait(interval)


def start()->dict:
    global _WORKER
    state=status()
    if not state["enabled"] or not state["configured_roots"]:
        return state
    with _LOCK:
        if _WORKER is None or not _WORKER.is_alive():
            _STOP.clear()
            _WORKER=threading.Thread(target=_loop,daemon=True,
                                     name="asterion-security-file-guardian")
            _WORKER.start()
    return status()


def stop()->None:
    global _WORKER
    _STOP.set()
    current=_WORKER
    if current:current.join(timeout=3)
    if current is None or not current.is_alive():_WORKER=None
