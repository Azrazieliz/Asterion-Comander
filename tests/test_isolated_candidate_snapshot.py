"""Actual staged-tree and opt-in real local container acceptance."""
import os
from pathlib import Path
import subprocess
import pytest
from asterion_remote.isolated_test_runner import _snapshot,IsolatedContainerTests

def git(root,*args):
    return subprocess.run(["git","-C",str(root),*args],check=True,capture_output=True,text=True).stdout.strip()

def fixture(root):
    root.mkdir()
    git(root,"init","-q")
    (root/"tests").mkdir()
    (root/"value.py").write_text("value=2\n",encoding="utf-8")
    (root/"tests"/"test_value.py").write_text(
        "from pathlib import Path\nfrom value import value\n"
        "def test_fixture():\n"
        "    assert value == 2\n"
        "    assert not Path('/src/.git').exists()\n"
        "    assert not Path('/src/local-secret.txt').exists()\n",encoding="utf-8")
    git(root,"add",".")

def test_snapshot_contains_exact_index_not_live_or_untracked(tmp_path):
    root=tmp_path/"work";fixture(root)
    (root/"value.py").write_text("value=999\n",encoding="utf-8")
    (root/"local-secret.txt").write_text("synthetic private data",encoding="utf-8")
    destination=tmp_path/"snapshot";destination.mkdir()
    tree=_snapshot(root,destination)
    assert tree==git(root,"write-tree")
    assert (destination/"value.py").read_text()=="value=2\n"
    assert not (destination/".git").exists()
    assert not (destination/"local-secret.txt").exists()

def test_real_container_accepts_pass_and_rejects_failure(tmp_path):
    image=os.environ.get("ASTERION_TEST_CONTAINER_IMAGE")
    if not image:pytest.skip("explicit pinned local test image not configured")
    root=tmp_path/"work";fixture(root)
    (root/"local-secret.txt").write_text("synthetic private data",encoding="utf-8")
    runner=IsolatedContainerTests(image,{"fixture1":["tests/test_value.py"]})
    passed=runner(root,"fixture1")
    assert passed["exit_code"]==0,passed
    assert passed["tree_sha"]==git(root,"write-tree")
    (root/"value.py").write_text("value=3\n",encoding="utf-8");git(root,"add","value.py")
    failed=runner(root,"fixture1")
    assert failed["exit_code"]==1,failed
    assert passed["receipt_sha256"]!=failed["receipt_sha256"]
