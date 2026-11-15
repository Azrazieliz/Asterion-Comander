"""Source-only Control AI integration verification; never builds or deploys APK.

This script is designed to be fetched by the existing authorized Windows
worker from a specific Git ref and executed against a temporary extracted
tree. It deliberately leaves the staging repository's dirty files, installed
Control runtime, Android signer, phone, credentials and other apps unchanged.

When executed with exec(git_show_bytes) from Windows, the caller sets
SOURCE_REPO = r'D:/AsterionControlUpgrade20261115' and source_ref=FETCH_HEAD.
"""
from __future__ import annotations

import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TESTS = [
    "test_overnight_supervisor.py",
    "test_control_ai_routes.py",
    "test_control_v2.py",
    "test_session_journal.py",
    "test_mixed_sessions.py",
    "test_vpn_route_policy.py",
    "test_model_evaluation.py",
    "test_local_mcp_client.py",
]


def main(repo: str, ref: str = "FETCH_HEAD") -> int:
    root_repo=Path(repo)
    if not root_repo.is_dir():
        print("SOURCE_REPO_NOT_FOUND")
        return 10
    with tempfile.TemporaryDirectory(prefix="asterion_control_source_check_") as temp:
        target=Path(temp)
        names=subprocess.check_output([
            "git","-C",str(root_repo),"ls-tree","-r","--name-only",
            ref,"--","asterion_remote","tests"
        ],timeout=20).decode("utf-8").splitlines()
        count=0
        for name in names:
            if not name.endswith(".py"):
                continue
            payload=subprocess.check_output([
                "git","-C",str(root_repo),"show",ref+":"+name
            ],timeout=15)
            file=target/name
            file.parent.mkdir(parents=True,exist_ok=True)
            file.write_bytes(payload)
            count+=1
        (target/"asterion_remote"/"static").mkdir(exist_ok=True)
        invalid=[]
        for source in target.rglob("*.py"):
            try:
                compile(source.read_bytes(),str(source),"exec")
            except SyntaxError as exc:
                invalid.append(str(source.relative_to(target))+": "+str(exc))
        print("SOURCE_FILES",count,"SYNTAX_ERRORS",len(invalid),flush=True)
        if invalid:
            for item in invalid[:10]:
                print("SYNTAX_ERROR",item,flush=True)
            return 11
        sys.path.insert(0,str(target))
        try:
            suite=unittest.TestSuite([
                unittest.defaultTestLoader.discover(str(target/"tests"),pattern=pattern)
                for pattern in TESTS])
            sink=io.StringIO()
            result=unittest.TextTestRunner(verbosity=0,stream=sink).run(suite)
            for test,trace in result.errors:
                print("ERROR_CASE",test.id(),repr(trace.splitlines()[-3:])[:350],
                      flush=True)
            for test,trace in result.failures:
                print("FAIL_CASE",test.id(),repr(trace.splitlines()[-3:])[:350],
                      flush=True)
            print("TESTS_RAN",result.testsRun,
                  "FAILED",len(result.failures),
                  "ERRORED",len(result.errors),
                  "PASS",result.wasSuccessful(),flush=True)
            return 0 if result.wasSuccessful() else 1
        finally:
            sys.path.remove(str(target))


if __name__ == "__main__":
    # Only execute explicitly from an authorized owner machine. Never
    # fetch/deploy or modify Windows worker services from this test script.
    if len(sys.argv) != 2:
        raise SystemExit("Usage: verify_control_ai_isolated.py <source-git-repo>")
    raise SystemExit(main(sys.argv[1]))
