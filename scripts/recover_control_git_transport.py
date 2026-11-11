"""One-shot, data-preserving recovery of the EXISTING Asterion Control Git transport.

Does not restart the native Windows listener, change ADB pairing, or touch APKs.
Run locally as the normal Windows user from the existing Control installation.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_URL = "https://github.com/Azrazieliz/Asterion-Control-Bridge.git"
SOURCE_BRANCH = "work/android-primary-continuation-observation-20261105"
PROOF_IDS = {
    "ac-20261111-1717-chatgpt-pcstatus-01",
    "ac-20261111-recover-phone-ui-proof-01",
}


def report(*parts):
    print("CONTROL_RECOVERY", *parts, flush=True)


def execute(args, *, cwd=None, check=True, timeout=120):
    p = subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True,
                       text=True, errors="replace", timeout=timeout)
    if check and p.returncode:
        raise RuntimeError(f"{args[0]} failed ({p.returncode}): "
                           + (p.stderr or p.stdout)[-750:])
    return p.stdout.rstrip('\r\n')


def git(repo, *args):
    return execute(["git", "-C", repo, *args])


def windows_processes():
    command = ("Get-CimInstance Win32_Process | "
               "Where-Object { $_.Name -in @('python.exe','pythonw.exe','powershell.exe','pwsh.exe') } | "
               "Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress")
    raw = execute(["powershell.exe", "-NoProfile", "-NonInteractive",
                   "-Command", command])
    if not raw:
        return []
    data = json.loads(raw)
    return data if isinstance(data, list) else [data]


def stop_only_git_bridge():
    processes = windows_processes()
    watchdogs = [p for p in processes
                 if str(p.get("Name", "")).lower() in ("powershell.exe", "pwsh.exe")
                 and "start_git_bridge.ps1" in str(p.get("CommandLine") or "").lower()]
    workers = [p for p in processes
               if str(p.get("Name", "")).lower() in ("python.exe", "pythonw.exe")
               and "asterion_remote.github_bridge_git" in str(p.get("CommandLine") or "").lower()]
    # Stop supervisor first to prevent it spawning a worker during Git recovery.
    for p in watchdogs + workers:
        execute(["taskkill", "/PID", str(p["ProcessId"]), "/F"],
                check=False, timeout=15)
    report("stopped_git_supervisors", len(watchdogs),
           "stopped_git_consumers", len(workers))


def backup(worktree, source, backup_dir):
    backup_dir.mkdir(parents=True, exist_ok=False)
    if (worktree / ".git").exists():
        shutil.copytree(worktree / ".git", backup_dir / "private-bridge-git")
    if (worktree / "results").exists():
        shutil.copytree(worktree / "results", backup_dir / "results")
    if source.exists():
        shutil.copy2(source, backup_dir / "github_bridge_git.py")
    report("backup", backup_dir)


def ensure_clean_enough(worktree, backup_dir):
    """Preserve local result changes and isolate unsubmitted command files.

    A running Git worker can leave 'M results/...' and '?? commands/active/...'.
    The former must be committed/published; the latter has not been accepted by
    the remote and must not be replayed. Move untracked commands into the
    recovery backup rather than deleting or automatically submitting them.
    """
    rows = git(worktree, "status", "--porcelain", "--untracked-files=all").splitlines()
    unrelated = []
    held = []
    for row in rows:
        status = row[:2]
        name = row[3:].strip().strip('"')
        if name.startswith("results/") and name.endswith(".json"):
            continue
        if status == "??" and name.startswith("commands/active/") and name.endswith(".json"):
            source = worktree / name
            if not source.is_file():
                unrelated.append(row)
                continue
            try:
                request = json.loads(source.read_text(encoding="utf8"))
            except (OSError, ValueError):
                unrelated.append(row)
                continue
            if request.get("id") != source.stem or not isinstance(request.get("op"), str):
                unrelated.append(row)
                continue
            held.append((name, source))
            continue
        unrelated.append(row)
    if unrelated:
        raise RuntimeError("Unrecognized local bridge changes (backup preserved): "
                           + repr(unrelated[:8]))
    if held:
        target = backup_dir / "held-unsubmitted-local-commands"
        target.mkdir(parents=True, exist_ok=True)
        for name, source in held:
            archived = target / Path(name).name
            if archived.exists():
                raise RuntimeError("Refusing to overwrite a held local command")
            shutil.move(str(source), str(archived))
        report("held_unsubmitted_local_commands", len(held),
               "backup", target)


def commit_results(worktree, label):
    git(worktree, "add", "--", "results")
    names = git(worktree, "diff", "--cached", "--name-only").splitlines()
    if any(not n.startswith("results/") or not n.endswith(".json")
           for n in names):
        raise RuntimeError("Refusing to commit non-receipt files")
    if names:
        git(worktree, "-c", "user.name=Asterion Control",
            "-c", "user.email=asterion-control@users.noreply.github.com",
            "commit", "-m", label)
    return len(names)


def sync_receipts(worktree):
    """Preserve unpublished local result commits; never hard-reset this checkout."""
    for attempt in range(12):
        git(worktree, "fetch", "--quiet", "origin", "main")
        ahead = int(git(worktree, "rev-list", "--count", "origin/main..HEAD"))
        if not ahead:
            git(worktree, "merge", "--ff-only", "origin/main")
            return
        paths = [n.strip() for n in
                 git(worktree, "log", "--format=", "--name-only",
                     "origin/main..HEAD").splitlines() if n.strip()]
        if not paths or any(not p.startswith("results/") or not p.endswith(".json")
                            for p in paths):
            raise RuntimeError("Unpublished local commits affect non-receipt files")
        try:
            git(worktree, "rebase", "origin/main")
        except Exception as e:
            raise RuntimeError("Cannot safely rebase results; backup preserved: " + str(e))
        try:
            git(worktree, "push", "--quiet", "origin", "HEAD:main")
            return
        except RuntimeError:
            report("concurrent_push_retry", attempt + 1)
            time.sleep(min(8, attempt + 1))
    raise RuntimeError("Result publication could not catch up with concurrent writers")


def quarantine_uncertain_backlog(worktree):
    """Hold stale, unacknowledged operations; preserve existing local receipts."""
    results = worktree / "results"
    results.mkdir(parents=True, exist_ok=True)
    held = []
    for commands in [worktree / "commands" / "active",
                     worktree / "commands"]:
        if not commands.is_dir():
            continue
        for path in sorted(commands.glob("*.json")):
            identity = path.stem
            if identity in PROOF_IDS or (results / path.name).exists():
                continue
            try:
                request = json.loads(path.read_text(encoding="utf8"))
            except (ValueError, OSError):
                continue
            if request.get("id") != identity:
                continue
            response = {
                "id": identity, "ok": False, "status": "uncertain",
                "error": "Unacknowledged before Git transport recovery; execution "
                         "not verified. Held to prevent unreviewed replay.",
            }
            (results / path.name).write_text(
                json.dumps(response, separators=(",", ":")), encoding="utf8")
            held.append(identity)
    count = commit_results(worktree, "Control recovery: preserve unacknowledged commands without replay")
    if count:
        sync_receipts(worktree)
    report("held_unacknowledged", len(held))


def install_existing_source_patch(root, backup_dir):
    """Fetch only the vetted Git transport source from the existing source repo."""
    source = root / "asterion_remote" / "github_bridge_git.py"
    git(root, "fetch", "--no-tags", "origin", SOURCE_BRANCH)
    data = subprocess.run(
        ["git", "-C", str(root), "show",
         "FETCH_HEAD:asterion_remote/github_bridge_git.py"],
        capture_output=True, timeout=35, check=True).stdout
    if len(data) < 10000 or b"def sync_remote():" not in data \
            or b"recover_unpublished()" not in data:
        raise RuntimeError("Fetched worker patch failed content checks")
    compile(data, str(source), "exec")
    temp = source.with_suffix(".py.recovery-new")
    with temp.open("wb") as out:
        out.write(data)
        out.flush()
        os.fsync(out.fileno())
    os.replace(temp, source)
    report("source_patch_installed", len(data), "bytes")


def start_existing_supervisor(root):
    launcher = root / "scripts" / "start_git_bridge.ps1"
    if not launcher.exists():
        raise RuntimeError("Existing start_git_bridge.ps1 missing")
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
        subprocess, "CREATE_NO_WINDOW", 0)
    p = subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-NonInteractive",
         "-ExecutionPolicy", "Bypass", "-File", str(launcher)],
        cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, creationflags=flags)
    report("git_supervisor_started_pid", p.pid)


def main():
    if os.name != "nt":
        raise RuntimeError("Run on the existing Windows Control PC")
    root = Path(os.environ.get("ASTERION_CONTROL_RELEASE",
                               r"D:\AsterionControlRelease"))
    state = Path(os.environ["LOCALAPPDATA"]) / "AsterionControl"
    worktree = Path(os.environ.get("ASTERION_BRIDGE_GIT_WORKTREE",
                                   str(state / "private-bridge-repo")))
    source = root / "asterion_remote" / "github_bridge_git.py"
    launcher = root / "scripts" / "start_git_bridge.ps1"
    if not (root / ".git").exists() or not source.exists() or not launcher.exists():
        raise RuntimeError("Existing Control source/launcher not found at " + str(root))
    if not (worktree / ".git").exists():
        raise RuntimeError("Original private bridge checkout not found at " + str(worktree))
    if git(worktree, "remote", "get-url", "origin").rstrip("/").lower() \
            != REPO_URL.lower():
        raise RuntimeError("Unexpected private bridge remote; refusing to touch checkout")
    stop_only_git_bridge()
    destination = Path(r"D:\AsterionControlRecovery") / datetime.now().strftime(
        "%Y%m%d-%H%M%S")
    backup(worktree, source, destination)
    gitdir = worktree / ".git"
    for name in ("rebase-merge", "rebase-apply"):
        if (gitdir / name).exists():
            git(worktree, "rebase", "--abort")
            report("aborted_interrupted_rebase", name)
    if (gitdir / "index.lock").exists():
        # Only this worker's processes were stopped; refuse if another Git is active.
        other_git = execute(["powershell.exe", "-NoProfile", "-Command",
                             "(Get-Process git -ErrorAction SilentlyContinue | Measure-Object).Count"])
        if other_git.strip() != "0":
            raise RuntimeError("Another Git process is running; lock kept")
        (gitdir / "index.lock").unlink()
        report("cleared_stale_index_lock")
    ensure_clean_enough(worktree, destination)
    committed = commit_results(worktree, "Control recovery: preserve unpublished local receipts")
    report("unpublished_receipts_preserved", committed)
    sync_receipts(worktree)
    quarantine_uncertain_backlog(worktree)
    install_existing_source_patch(root, destination)
    start_existing_supervisor(root)
    proof = worktree / "results" / "ac-20261111-recover-phone-ui-proof-01.json"
    for _ in range(45):
        if proof.exists():
            try:
                record = json.loads(proof.read_text("utf8"))
                if record.get("status") == "complete" and record.get("ok"):
                    report("PHONE_UI_CONFIRMED", "yes")
                    return 0
                report("PHONE_UI_RECEIPT", record.get("status"), record.get("error", ""))
                return 2
            except (OSError, ValueError):
                pass
        time.sleep(2)
    report("PHONE_UI_CONFIRMED", "no", "inspect Git supervisor logs and result publication")
    return 3


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        report("ERROR", type(exc).__name__, str(exc))
        sys.exit(1)
