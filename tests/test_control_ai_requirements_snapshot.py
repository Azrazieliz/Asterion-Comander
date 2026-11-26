"""Owner/legacy source-correctness and immutable requirements-index regressions.

Do not treat passing tests as model intelligence or Android acceptance.
"""
from pathlib import Path
import json

import pytest

from scripts.control_ai_requirements_snapshot import git_blob_sha,snapshot

ROOT=Path(__file__).resolve().parents[1]
INDEX=ROOT/"docs/CONTROL_AI_REQUIREMENT_ANCHORS_20261126.json"


def index():
    return json.loads(INDEX.read_text(encoding="utf-8"))


def test_source_locked_owner_and_v3_v6_contracts_recover_exactly():
    result=snapshot(ROOT,index(),max_pack_chars=12000)
    assert result["mandatory_count"]==25
    assert result["source_count"]==7
    assert len(result["partitions"])>=2
    assert result["original_source_spans_verified"]
    assert not result["all_requirements_certified"]
    assert not result["all_v3_v6_approved_scope_covered"]
    assert not result["device_accepted"]
    assert {f"OAI-{n:02d}" for n in range(1,16)} <= set(result["mandatory_ids"])
    # Every source reference retains lines and exact SHA-256 passage identity.
    all_records=[record for block in result["partitions"] for record in block]
    assert all(len(row["span_sha256"])==64 and len(row["sha256"])==64 and
               row["start_line"]<=row["end_line"] and row["text"].strip()
               for row in all_records)
    assert "SmolLM3-3B is diagnostic" in next(x["text"] for x in all_records
              if x["id"]=="OAI-02")
    assert "rights-cleared" in next(x["text"] for x in all_records
              if x["id"]=="OAI-03")
    assert "TeraBox" in next(x["text"] for x in all_records
              if x["id"]=="OAI-05")
    assert "50,000 unique sealed holdout" in next(x["text"] for x in all_records
              if x["id"]=="OAI-12")


def test_locked_source_modified_refuses_silent_reconciliation(tmp_path):
    root=tmp_path/"root"; root.mkdir()
    (root/"docs").mkdir()
    data="## Tested owner decision\nPreserve original authorized Control.\n"
    path=root/"docs/owner.md";path.write_text(data,encoding="utf8")
    scheme={
        "schema_version":"asterion.control.requirement-anchors/1",
        "files":{"owner":{"path":"docs/owner.md","blob_sha":git_blob_sha(data.encode())}},
        "records":[{"id":"owner-test","file":"owner","start_match":"## Tested owner decision",
                    "end_before":None,"topic":"owner.test","kind":"requirement",
                    "status":"active","importance":"mandatory","supersedes":[]}],
        "required_topics":["owner.test"]}
    assert snapshot(root,scheme)["mandatory_ids"]==["owner-test"]
    path.write_text(data+"Unapproved source mutation\n",encoding="utf8")
    with pytest.raises(ValueError,match="pinned_canonical_source_changed"):
        snapshot(root,scheme)
    path.write_text(data,encoding="utf8")
    scheme["records"][0]["start_match"]="Nonexistent heading"
    with pytest.raises(ValueError,match="anchor_missing_or_ambiguous"):
        snapshot(root,scheme)


def test_no_silent_requirement_deletion_or_duplicate_source_span(tmp_path):
    root=tmp_path/"root";root.mkdir();(root/"docs").mkdir()
    content="## Authorized decision\nDecision is binding.\n"
    (root/"docs/source.md").write_text(content)
    base={
        "schema_version":"asterion.control.requirement-anchors/1",
        "files":{"source":{"path":"docs/source.md","blob_sha":git_blob_sha(content.encode())}},
        "records":[{"id":"approved-01","file":"source","start_match":"## Authorized decision",
                    "end_before":None,"topic":"decision.critical","kind":"constraint",
                    "status":"active","importance":"mandatory","supersedes":[]}],
        "required_topics":["decision.critical"]}
    assert snapshot(root,base)["mandatory_count"]==1
    base["required_topics"]=["decision.critical","missing.owner.scope"]
    with pytest.raises(ValueError,match="mandatory_owner_requirement_coverage_missing"):
        snapshot(root,base)
    base["required_topics"]=["decision.critical"]
    base["records"].append(dict(base["records"][0]))
    with pytest.raises(ValueError,match="duplicate_requirement_id"):
        snapshot(root,base)
