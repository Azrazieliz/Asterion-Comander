"""Real OS process-lock regression: no production service, credentials or phone."""
from pathlib import Path
import subprocess
import sys
import queue
import threading

import pytest

from asterion_remote.bridge_worker_lock import worker_process_lock, WorkerAlreadyRunning

ROOT = Path(__file__).resolve().parents[1]
CHILD = """
import sys
from pathlib import Path
from asterion_remote.bridge_worker_lock import worker_process_lock
with worker_process_lock(Path(sys.argv[1])):
    print('locked', flush=True)
    sys.stdin.read()
"""


def test_exclusion_and_release_after_abrupt_process_exit(tmp_path):
    lock = tmp_path / "relay.lock"
    for _ in range(3):
        child = subprocess.Popen([sys.executable, "-c", CHILD, str(lock)],
            cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True)
        try:
            # Child signals only after taking the actual lock; do not race
            # the child for ownership while it starts.
            ready=queue.Queue()
            reader=threading.Thread(target=lambda: ready.put(child.stdout.readline()),daemon=True)
            reader.start()
            assert ready.get(timeout=10).strip()=="locked"
            with pytest.raises(WorkerAlreadyRunning):
                with worker_process_lock(lock):
                    pytest.fail("Duplicate worker acquired a live queue")
            child.kill()
            child.wait(timeout=10)
            assert lock.exists(), "A crash must not require deleting the lock file"
            with worker_process_lock(lock):
                pass
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=10)
            child.stdin.close()
            child.stdout.close()
            child.stderr.close()


def test_worker_main_does_not_touch_heartbeat_when_duplicate(tmp_path, monkeypatch):
    from asterion_remote import github_bridge_git as worker
    lock = tmp_path / "relay.lock"
    monkeypatch.setattr(worker, "WORKER_LOCK", lock)
    monkeypatch.setattr(worker, "_run_owned_worker", lambda: pytest.fail("Duplicate started"))
    with worker_process_lock(lock):
        worker.main()


def test_existing_running_receipt_rejects_repeated_dispatch(tmp_path, monkeypatch):
    from asterion_remote import github_bridge_git as worker
    monkeypatch.setattr(worker, "ROOT", tmp_path)
    assert worker.write_result("once-only-job", {"id":"once-only-job","ok":False,
        "status":"running"}, publish_now=False)
    assert not worker.write_result("once-only-job", {"id":"once-only-job","ok":False,
        "status":"running"}, publish_now=False)
