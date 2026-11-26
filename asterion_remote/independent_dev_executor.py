"""Fail-closed isolated source candidate executor for existing overnight cycles.

An independent local model may propose exactly ONE file replacement with a
baseline SHA. It cannot choose paths, commands, credentials, branches, tests or
production promotion. All work happens in an isolated git worktree. Tests that
execute candidate code require an external configured sandbox; without one,
only static checks run and the candidate is explicitly NOT source-tested.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Callable

_HASH = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[a-zA-Z0-9_.-]{8,100}$")
_ALLOWED_EXT = {".py", ".java", ".cpp", ".h", ".json", ".md"}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(root: Path, *args: str, timeout: int = 60) -> str:
    result = subprocess.run(["git", "-C", str(root), *args],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        errors="replace", timeout=timeout, check=False,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    if result.returncode:
        raise RuntimeError("git_" + args[0] + "_failed: " + result.stderr[-400:])
    return result.stdout.strip()


class CandidateExecutor:
    def __init__(self, canonical_root, isolated_root, *, sandbox_test=None):
        self.canonical = Path(canonical_root).resolve(strict=True)
        self.isolated = Path(isolated_root).resolve()
        if self.isolated == self.canonical or self.canonical in self.isolated.parents:
            raise ValueError("sandbox_must_be_outside_canonical_source")
        if not (self.canonical / ".git").exists():
            raise ValueError("canonical_repository_required")
        self.isolated.mkdir(parents=True, exist_ok=True)
        # sandbox_test(worktree, expected_test_id) -> {exit_code, receipt_sha256,
        # runner_kind}. This callback MUST execute untrusted candidate tests
        # in a real, separately authenticated/isolation-verified sandbox.
        # No sandbox: syntax/diff checks only; no functional certification.
        self.sandbox_test = sandbox_test

    def _check_candidate(self, content: str, task: dict) -> tuple[Path, bytes, str]:
        if not isinstance(content, str) or len(content) > 500000:
            raise ValueError("invalid_local_model_edit")
        try:
            edit = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("model_must_return_machine_readable_json") from exc
        if not isinstance(edit, dict) or set(edit) != {
            "task_id","target_path","expected_sha256","replacement","next_work"}:
            raise ValueError("model_candidate_schema_mismatch")
        if edit["task_id"] != task["task_id"] or edit["target_path"] != task["target_path"]:
            raise ValueError("model_attempted_out_of_scope_edit")
        if not isinstance(edit["replacement"], str) or not 1 <= len(edit["replacement"]) <= 200000:
            raise ValueError("invalid_replacement_size")
        if not isinstance(edit["next_work"], str) or not 3 <= len(edit["next_work"]) <= 2000:
            raise ValueError("invalid_next_work")
        path = Path(task["target_path"])
        if path.is_absolute() or ".." in path.parts or path.suffix not in _ALLOWED_EXT:
            raise ValueError("target_not_in_verified_source_allowlist")
        if not (path.parts[0] in {"asterion_remote","android","scripts","tests"}):
            raise ValueError("unapproved_source_root")
        if path.as_posix() != task["target_path"]:
            raise ValueError("noncanonical_target_path")
        if not _HASH.fullmatch(edit["expected_sha256"]):
            raise ValueError("expected_sha256_required")
        replacement = edit["replacement"].encode("utf-8")
        if path.suffix==".py":
            ast.parse(edit["replacement"],filename=str(path))
        elif path.suffix==".json":
            json.loads(edit["replacement"])
        return path,replacement,edit["next_work"]

    def run(self, content: str, cycle_id: str, request_id: str, task: dict) -> dict:
        if not _SAFE_ID.fullmatch(request_id):
            raise ValueError("invalid_unique_turn_id")
        rel, replacement, next_work = self._check_candidate(content, task)
        proposal = json.loads(content)
        candidate_dir = self.isolated / request_id
        if candidate_dir.exists():
            raise RuntimeError("candidate_worktree_exists_outcome_uncertain")
        # Never attach to a dirty/uncertain canonical checkout; use pinned HEAD.
        baseline = _git(self.canonical, "rev-parse", "HEAD")
        if not re.fullmatch(r"[0-9a-f]{40}", baseline):
            raise RuntimeError("unverified_baseline_commit")
        _git(self.canonical,"worktree","add","--detach",
             str(candidate_dir),baseline,timeout=90)
        target=candidate_dir / rel
        if target.is_symlink() or not target.is_file() or candidate_dir not in target.resolve().parents:
            raise ValueError("candidate_target_missing_or_unsafe")
        prior=target.read_bytes()
        if _sha(prior)!=proposal["expected_sha256"]:
            raise ValueError("candidate_outdated_source_sha")
        if prior==replacement:
            raise ValueError("candidate_has_no_changes")
        target.write_bytes(replacement)
        _git(candidate_dir,"add","--",rel.as_posix())
        _git(candidate_dir,"diff","--cached","--check")
        if self.sandbox_test is None:
            raise RuntimeError("independent_test_sandbox_not_verified")
        test = self.sandbox_test(candidate_dir,task["task_id"])
        if (not isinstance(test,dict) or test.get("exit_code")!=0 or
            not _HASH.fullmatch(str(test.get("receipt_sha256",""))) or
            test.get("runner_kind") not in {"isolated_container","isolated_vm"}):
            raise RuntimeError("candidate_functional_tests_not_verified")
        _git(candidate_dir,"-c","user.name=Asterion Control Candidate",
             "-c","user.email=control-candidate@localhost.invalid",
             "commit","-m","AI candidate: "+task["task_id"],timeout=70)
        commit=_git(candidate_dir,"rev-parse","HEAD")
        if not re.fullmatch(r"[a-f0-9]{40}",commit):
            raise RuntimeError("candidate_commit_missing")
        receipt = _sha(json.dumps({
            "baseline":baseline,"candidate_commit":commit,
            "path":rel.as_posix(),"file_sha256":_sha(replacement),
            "test_receipt":test["receipt_sha256"],"runner_kind":test["runner_kind"],
            "production_promoted":False},sort_keys=True).encode("utf-8"))
        return {"candidate_commit":commit,"evidence_sha256":receipt,
                "work_summary":"Isolated candidate "+commit[:12]+
                    " changed "+rel.as_posix()+"; verified isolated tests; NOT installed",
                "next_work":next_work,"done":False,"acceptance_verified":False,
                "verification_level":"source_tested"}


def source_context(canonical_root, task, *, max_chars=20000) -> str:
    """Ground model work in exactly the task-owned source; no broad credential reads."""
    path=Path(canonical_root).resolve() / task["target_path"]
    if path.is_symlink() or not path.is_file() or path.stat().st_size>200000:
        raise ValueError("source_not_safely_readable")
    data=path.read_bytes()
    source=data.decode("utf-8")
    if len(source)>max_chars:
        raise ValueError("source_exceeds_model_context_budget")
    return json.dumps({"task_id":task["task_id"],
        "goal":task["goal"],"file":task["target_path"],
        "sha256":_sha(data),"source":source},ensure_ascii=False)
