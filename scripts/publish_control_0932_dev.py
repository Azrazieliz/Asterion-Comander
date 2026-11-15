"""Publish ONLY the previously owner-signed, checksum-verified Control v0.9.32 build.

This creates a source-branch artifact, NOT an automatic installed update and
NOT a promotion of unverified features to the production update feed.
Never signs with a new key, changes a paired device or overwrites main.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRANCH = "work/control-0927-overnight-cycles-20261111"
APK = "dist/Asterion-Control-v0.9.32-release.apk"
SUM = "dist/SHA256SUMS-v0.9.32.txt"
EXPECTED = "ee631c4b6e075d1ce67f28cfb78db83b37a325ef81c009081800596de7ee796f"
BYTES = 14208156


def git(*args: str) -> str:
    p = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True,
        check=True, timeout=120)
    return p.stdout.strip()


def main() -> None:
    if git("branch", "--show-current") != BRANCH:
        raise RuntimeError("unexpected_control_branch")
    local = git("rev-parse", "HEAD")
    remote = git("ls-remote", "origin", "refs/heads/" + BRANCH).split()[0]
    if local != remote:
        raise RuntimeError("source_branch_advanced_reconcile_before_publishing")
    if git("status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError("tracked_source_changes_not_reviewed")
    data = (ROOT / APK).read_bytes()
    if len(data) != BYTES or hashlib.sha256(data).hexdigest() != EXPECTED:
        raise RuntimeError("owner_signed_package_digest_mismatch")
    manifest = (ROOT / SUM).read_text("utf8").strip()
    if manifest != EXPECTED + "  Asterion-Control-v0.9.32-release.apk":
        raise RuntimeError("release_sha256_manifest_mismatch")
    build = (ROOT / "android/app/build.gradle").read_text("utf8")
    if "versionCode 932" not in build or "versionName '0.9.32'" not in build:
        raise RuntimeError("android_version_not_matching_release")
    git("add", "--", APK, SUM)
    staged = git("diff", "--cached", "--name-only").splitlines()
    if sorted(staged) != sorted([APK, SUM]):
        raise RuntimeError("unexpected_staged_release_files")
    git("-c", "user.name=Asterion Control Owner Build",
        "-c", "user.email=build@users.noreply.github.com",
        "commit", "-m", "Publish checksum-verified owner-signed Control 0.9.32 dev APK")
    git("push", "origin", "HEAD:" + BRANCH)
    print("CONTROL_0932_DEV_APK_PUBLISHED sha256=" + EXPECTED +
          " branch=" + BRANCH + " commit=" + git("rev-parse", "HEAD"),
          flush=True)


if __name__ == "__main__":
    main()
