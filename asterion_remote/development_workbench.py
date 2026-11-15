"""Actual isolated Git workbench for Asterion's continuous development cycles.

Executes *source changes*, not model-authored shell commands. Owner config
binds each project to an EXISTING local Git checkout, a pinned baseline
branch, permitted file prefixes and optional push to a dedicated AI branch.

Changes always occur inside a NEW temporary Git worktree, never the owner's
original working tree. A successfully verified commit remains on the cycle
branch for the next turn. Git push is opt-in at the owner registry level.
All inputs are treated as untrusted model output.

Proof here means: changed bytes match an actual local Git commit, Git diff
integrity and safe static parse checks pass. This does NOT prove behavioral
tests, app correctness, signing, release quality, or device acceptance.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

_PROJECT = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{3,63}$")
_SHA = re.compile(r"^[a-f0-9]{64}$")
_MAX_PATCHES = 8
_MAX_NEW_BYTES = 100_000
_MAX_TOTAL_BYTES = 250_000
_MAX_CONTEXT = 16000
_SUFFIXES = {
    ".py", ".java", ".kt", ".js", ".ts", ".tsx", ".json", ".xml", ".yml",
    ".yaml", ".md", ".toml", ".gradle", ".sql", ".c", ".cpp", ".h",
    ".hpp", ".css", ".html", ".txt",
}


@dataclass(frozen=True)
class GitProject:
    name: str
    repository: Path
    base_ref: str
    allowed_prefixes: tuple[str, ...]
    push_to_origin: bool = False
    remote: str = "origin"

    def __post_init__(self):
        if not _PROJECT.fullmatch(self.name):
            raise ValueError("invalid_project_name")
        if not isinstance(self.repository, Path) or not self.repository.is_absolute():
            raise ValueError("absolute_repository_path_required")
        if not isinstance(self.base_ref,str) or not re.fullmatch(
                r"[A-Za-z0-9_./-]{3,120}",self.base_ref) or ".." in self.base_ref:
            raise ValueError("invalid_owner_pinned_git_base_ref")
        if (not self.allowed_prefixes or len(self.allowed_prefixes)>20 or
            any(not _valid_rel(p, is_prefix=True) for p in self.allowed_prefixes)):
            raise ValueError("invalid_owner_approved_file_prefixes")
        if self.remote!="origin":
            raise ValueError("only_owner_configured_origin_supported")


def _valid_rel(value: str, *, is_prefix: bool = False) -> bool:
    if not isinstance(value,str) or not value or len(value)>160:
        return False
    if "\\" in value or value.startswith("/") or "\x00" in value or "//" in value:
        return False
    p=PurePosixPath(value)
    if any(segment in ("",".","..") or segment.startswith(".")
           for segment in p.parts):
        return False
    if any(segment.lower() in {"secrets","credentials","keystore",
                                "private_keys","private-keys"}
           for segment in p.parts):
        return False
    if is_prefix:
        return True
    return p.suffix.lower() in _SUFFIXES


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _git(repo: Path, *args: str, timeout: float = 30) -> str:
    run=subprocess.run(
        ["git","-C",str(repo),*args],stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,
        timeout=timeout,check=False)
    if run.returncode:
        # Do not reflect Git remote URL credentials / arbitrary repo contents.
        raise RuntimeError("git_operation_failed_"+str(run.returncode))
    try:
        return run.stdout.decode("utf-8",errors="strict").strip()
    except UnicodeDecodeError as exc:
        raise RuntimeError("git_non_utf8_response") from exc


def _require_repo(policy: GitProject) -> Path:
    root=policy.repository.resolve(strict=True)
    true=Path(_git(root,"rev-parse","--show-toplevel")).resolve(strict=True)
    if true!=root or not (root/".git").exists():
        raise ValueError("owner_git_checkout_root_required")
    return root


def _within(path: str, policy: GitProject) -> bool:
    if not _valid_rel(path):
        return False
    return any(path.startswith(prefix.rstrip("/")+"/")
               for prefix in policy.allowed_prefixes)


def _file(worktree: Path, relative: str, policy: GitProject) -> Path:
    if not _within(relative,policy):
        raise PermissionError("ai_patch_not_in_owner_approved_source_roots")
    destination=worktree.joinpath(*PurePosixPath(relative).parts)
    for parent in [*destination.parents]:
        if parent==worktree.parent:break
        if parent.is_symlink():
            raise PermissionError("symlink_ancestor_forbidden")
    if destination.exists() and (destination.is_symlink() or
                                  not destination.is_file()):
        raise PermissionError("non_regular_source_forbidden")
    if not destination.resolve().is_relative_to(worktree.resolve()):
        raise PermissionError("source_path_escaped_git_worktree")
    return destination


def _plan(text: str) -> dict:
    if not isinstance(text,str) or len(text)>300_000:
        raise ValueError("invalid_model_development_plan")
    try:doc=json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("model_did_not_submit_structured_patch") from exc
    if not isinstance(doc,dict) or doc.get("schema")!=1:
        raise ValueError("unsupported_development_plan_schema")
    edits=doc.get("edits")
    if not isinstance(edits,list) or not 1<=len(edits)<=_MAX_PATCHES:
        raise ValueError("development_plan_requires_real_edits")
    next_work=doc.get("next_work")
    if not isinstance(next_work,str) or not 8<=len(next_work)<=1500:
        raise ValueError("continuation_description_required")
    if doc.get("done") is True:
        # A model cannot determine acceptance by asserting "done".
        raise ValueError("model_cannot_certify_project_completion")
    return doc


def _parse_and_apply(worktree: Path, policy: GitProject, text: str) -> list[dict]:
    doc=_plan(text)
    seen=set()
    verified=[]
    total=0
    for edit in doc["edits"]:
        if not isinstance(edit,dict):
            raise ValueError("invalid_patch_item")
        path=edit.get("path")
        expected=edit.get("expected_sha256")
        search=edit.get("replace")
        newfile=edit.get("create")
        if not isinstance(path,str) or path in seen:
            raise ValueError("duplicate_or_invalid_patch_path")
        seen.add(path)
        target=_file(worktree,path,policy)
        if not isinstance(expected,str) or (expected and not _SHA.fullmatch(expected)):
            raise ValueError("expected_old_source_sha256_required")
        exists=target.exists()
        if exists:
            if not expected:
                raise ValueError("existing_file_requires_exact_sha256")
            original=target.read_bytes()
            if _sha(original)!=expected:
                raise RuntimeError("source_changed_since_model_observation")
            if not isinstance(search,dict) or newfile is not None:
                raise ValueError("existing_file_requires_exact_replacement")
            old=search.get("old")
            new=search.get("new")
            if not isinstance(old,str) or not isinstance(new,str) or not old:
                raise ValueError("replacement_requires_old_and_new_text")
            try:previous=original.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("source_must_be_utf8") from exc
            if previous.count(old)!=1:
                raise ValueError("replacement_must_match_exactly_once")
            changed=previous.replace(old,new,1)
            output=changed.encode("utf-8")
        else:
            if expected or search is not None:
                raise ValueError("new_file_must_be_explicit_creation")
            if not isinstance(newfile,str) or not newfile:
                raise ValueError("new_file_content_required")
            output=newfile.encode("utf-8")
            target.parent.mkdir(parents=True,exist_ok=True)
            # After mkdir ensure no symlink ancestor was introduced.
            _file(worktree,path,policy)
        if (len(output)>_MAX_NEW_BYTES or b"\0" in output or
            output==target.read_bytes() if exists else False):
            raise ValueError("invalid_or_unchanged_patch_bytes")
        # Explicit checks avoid the conditional's precedence ambiguity.
        if len(output)>_MAX_NEW_BYTES or b"\0" in output:
            raise ValueError("source_file_size_or_binary_not_permitted")
        total+=len(output)
        if total>_MAX_TOTAL_BYTES:
            raise ValueError("total_patch_size_budget_exceeded")
        # Symlink races matter: open an existing regular file only after
        # rechecking the destination; owner repository is locally trusted.
        _file(worktree,path,policy)
        target.write_bytes(output)
        verified.append({"path":path,"sha256":_sha(output),"bytes":len(output)})
    return verified


def _static_verify(worktree:Path,changed:list[dict])->dict:
    checked=0
    for item in changed:
        target=worktree.joinpath(*PurePosixPath(item["path"]).parts)
        raw=target.read_bytes()
        if _sha(raw)!=item["sha256"]:
            raise RuntimeError("patch_readback_mismatch")
        suffix=target.suffix.lower()
        if suffix==".py":
            compile(raw,str(target),"exec")  # NO execution of model code
            checked+=1
        elif suffix==".json":
            json.loads(raw)
            checked+=1
        elif suffix==".xml":
            import xml.etree.ElementTree as ET
            ET.fromstring(raw)
            checked+=1
    _git(worktree,"diff","--check")
    return {"syntax_or_data_parsed":checked,
            "git_whitespace_integrity_checked":True,
            "functional_tests_executed":False,
            "device_tests_executed":False}


def _branch(cycle_id:str)->str:
    if not _PROJECT.fullmatch(cycle_id):
        raise ValueError("invalid_cycle_id")
    # Avoid invalid Git refs and collisions with other development projects.
    slug=re.sub(r"[^A-Za-z0-9_-]","-",cycle_id).strip("-")
    return "work/asterion-ai/"+slug[:40]+"-"+_sha(cycle_id.encode())[:10]


def project_context(policy:GitProject,focus_paths:tuple[str,...])->str:
    """Existing source excerpts with SHA pins for model replacements."""
    root=_require_repo(policy)
    if not 1<=len(focus_paths)<=8:
        raise ValueError("approved_focus_paths_required")
    branch=_branch(policy.name)
    try:
        _git(root,"rev-parse","--verify","refs/heads/"+branch)
        baseline=branch
    except RuntimeError:
        baseline=policy.base_ref
    result=[f"Git project: {policy.name}; baseline: {baseline}",
            "Only edit the files shown or add files beneath approved prefixes.",
            "Submit JSON schema=1, edits with exact old SHA256 and "
            "replace.old/replace.new or create for absent files. "
            "Always provide next_work; do not claim done."]
    remaining=_MAX_CONTEXT
    for path in focus_paths:
        if not _within(path,policy):
            raise PermissionError("focus_file_outside_owner_approved_roots")
        try:
            raw=subprocess.run(
                ["git","-C",str(root),"show",baseline+":"+path],
                stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=20)
            if raw.returncode:
                result.append("NEW_FILE "+path)
                continue
            if len(raw.stdout)>100_000:
                result.append("TOO_LARGE "+path)
                continue
            text=raw.stdout.decode("utf-8")
        except UnicodeDecodeError:
            result.append("BINARY_FILE "+path)
            continue
        budget=min(remaining,5000)
        result.append("FILE "+path+" SHA256 "+_sha(raw.stdout)+"\n"+
                      text[:budget])
        remaining-=min(len(text),budget)
        if remaining<=0:break
    return "\n\n".join(result)


def apply_verified_draft(policy:GitProject,model_output:str,
                         cycle_id:str,request_id:str)->dict:
    """Write real isolated code, compile/parse, commit, optionally push.

    The receipt proves a new reviewable Git commit with readback content,
    never that model-authored code passes functional or device acceptance.
    """
    root=_require_repo(policy)
    if cycle_id!=policy.name:
        raise PermissionError("cycle_not_authorized_for_git_project")
    if not re.fullmatch(re.escape(cycle_id)+r"-turn-[1-9][0-9]*",request_id):
        raise ValueError("invalid_development_turn_receipt")
    branch=_branch(cycle_id)
    # Ensure model produced a syntactically valid bounded plan before any git
    # worktree is created or owner repo metadata is modified.
    plan=_plan(model_output)
    start_sha=_git(root,"rev-parse","--verify",policy.base_ref)
    try:
        old_sha=_git(root,"rev-parse","--verify","refs/heads/"+branch)
        first=False
    except RuntimeError:
        old_sha=start_sha
        first=True
    with tempfile.TemporaryDirectory(prefix="asterion-dev-worktree-") as dirname:
        work=Path(dirname)
        args=("worktree","add","--detach",str(work),old_sha)
        _git(root,*args,timeout=60)
        try:
            changed=_parse_and_apply(work,policy,model_output)
            checks=_static_verify(work,changed)
            _git(work,"add","--",*[x["path"] for x in changed])
            staged=_git(work,"diff","--cached","--name-only").splitlines()
            if set(staged)!={x["path"] for x in changed}:
                raise RuntimeError("unexpected_git_staging")
            _git(work,"diff","--cached","--check")
            # Explicit no-hook and no signing options. Never execute a
            # repository-provided arbitrary hook during a model code commit.
            disabled_hooks=work/".asterion-disabled-hooks"
            disabled_hooks.mkdir(exist_ok=True)
            _git(work,"-c",f"core.hooksPath={disabled_hooks}",
                 "-c","commit.gpgsign=false",
                 "-c","user.name=Asterion Control AI Draft",
                 "-c","user.email=asterion-control@invalid",
                 "commit","-m",f"draft({cycle_id}): verified source turn {request_id}",
                 timeout=40)
            commit=_git(work,"rev-parse","HEAD")
            if not re.fullmatch(r"[0-9a-f]{40,64}",commit):
                raise RuntimeError("invalid_git_commit_receipt")
            for item in changed:
                raw=subprocess.run(["git","-C",str(work),"show",
                    commit+":"+item["path"]],stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,timeout=20)
                if raw.returncode or _sha(raw.stdout)!=item["sha256"]:
                    raise RuntimeError("git_committed_content_readback_mismatch")
            # CAS prevents overwriting a concurrently modified AI branch.
            _git(root,"update-ref","refs/heads/"+branch,commit,
                 old_sha if not first else "0"*40)
            if policy.push_to_origin:
                _git(root,"push",policy.remote,
                     "refs/heads/"+branch+":refs/heads/"+branch,
                     timeout=120)
                remote=_git(root,"ls-remote",policy.remote,
                            "refs/heads/"+branch,timeout=50)
                if not remote or remote.split()[0]!=commit:
                    raise RuntimeError("remote_push_not_independently_verified")
            evidence={
                "project":policy.name,"request_id":request_id,
                "baseline":old_sha,"commit":commit,"branch":branch,
                "files":changed,"static_checks":checks,
                "pushed_verified":policy.push_to_origin}
            proof=_sha(json.dumps(evidence,sort_keys=True).encode("utf-8"))
            return {
                "evidence_sha256":proof,
                "work_summary":(
                    f"Created Git source draft {commit[:12]} on {branch}; "
                    f"{len(changed)} changed file(s), committed file bytes "
                    "read back and independently SHA-256 verified. "
                    "Static checks passed; functional/device tests PENDING."
                ),
                "next_work":plan["next_work"],
                "done":False,
                "acceptance_verified":False,
                "draft_branch":branch,
                "draft_commit":commit,
                "static_checks":checks,
                "pushed_verified":policy.push_to_origin,
            }
        finally:
            # Worktree removed, original checkout untouched. The persisted
            # Git ref keeps successful draft commits reachable for inspection.
            _git(root,"worktree","remove","--force",str(work),timeout=40)
