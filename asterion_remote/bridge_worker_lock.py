"""OS-owned process exclusion for the original private Git relay.

The existing PowerShell supervisor mutex remains. This lock also prevents
manual/direct Python launches from acquiring the same owner-local command
queue. A process crash releases the kernel lock; the lock file is never
removed or treated as a stale-PID sentinel.
"""
from __future__ import annotations

import errno
import os
from contextlib import contextmanager
from pathlib import Path


class WorkerAlreadyRunning(RuntimeError):
    """A second worker must exit without changing receipts or heartbeat."""


@contextmanager
def worker_process_lock(path: Path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        # Windows locks a real byte. Never truncate an existing lock file.
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                if exc.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                    raise WorkerAlreadyRunning("Private Control relay already owns the queue") from exc
                raise
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise WorkerAlreadyRunning("Private Control relay already owns the queue") from exc
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
