"""Local, no-network container test gate for Control's independent candidates.

Requires a PRE-EXISTING pinned image with Python and tests installed. The
candidate model never supplies Docker arguments, commands, paths or image name.
No container installed means hard BLOCKED, never a simulated test receipt.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess


class IsolatedContainerTests:
    def __init__(self, image_digest, task_tests, *, timeout_s=180):
        if not isinstance(image_digest,str) or not re.fullmatch(
                r"sha256:[0-9a-f]{64}",image_digest):
            raise ValueError("pinned_local_image_id_required")
        if not isinstance(task_tests,dict) or not task_tests:
            raise ValueError("trusted_test_map_required")
        if not 10 <= timeout_s <= 600:
            raise ValueError("invalid_test_time_budget")
        for key,paths in task_tests.items():
            if not re.fullmatch(r"[a-z][a-z0-9_-]{3,79}",key):
                raise ValueError("invalid_test_task")
            if not isinstance(paths,list) or not paths:
                raise ValueError("no_trusted_tests")
            for path in paths:
                p=Path(path)
                if (p.is_absolute() or ".." in p.parts or
                        len(p.parts)!=2 or p.parts[0]!="tests" or
                        not p.name.startswith("test_") or p.suffix!=".py"):
                    raise ValueError("unapproved_test_path")
        if shutil.which("docker") is None:
            raise RuntimeError("local_container_runtime_not_available")
        self.image=image_digest
        self.tests=task_tests
        self.timeout_s=timeout_s

    def __call__(self, worktree, task_id):
        test_paths=self.tests.get(task_id)
        if not test_paths:
            raise ValueError("task_has_no_reviewed_test_suite")
        worktree=Path(worktree).resolve(strict=True)
        for p in test_paths:
            if not (worktree/p).is_file():
                raise ValueError("trusted_test_missing")
        argv=[
            "docker","run","--rm","--pull=never","--network=none",
            "--read-only","--cap-drop=ALL","--security-opt=no-new-privileges",
            "--pids-limit=128","--memory=1536m","--cpus=2",
            "--tmpfs","/tmp:rw,noexec,nosuid,size=256m",
            "--mount",f"type=bind,source={worktree},target=/src,readonly",
            "--workdir","/src","--user","65534:65534",
            "--env","PYTHONDONTWRITEBYTECODE=1","--env","PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
            self.image,"python","-m","pytest","-q",*test_paths
        ]
        process=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,
            timeout=self.timeout_s,check=False)
        receipt=hashlib.sha256(
            b"ASTERION-ISOLATED-TEST-V1\0"+str(process.returncode).encode()+
            b"\0"+process.stdout[-50000:]+b"\0"+process.stderr[-50000:]).hexdigest()
        return {"exit_code":process.returncode,
                "receipt_sha256":receipt,"runner_kind":"isolated_container",
                "output_tail":process.stdout[-1000:].decode("utf-8","replace")}
