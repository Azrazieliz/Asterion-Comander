"""Canonical V6 acceptance excerpts never vanish due to context window pressure."""
import hashlib
from pathlib import Path
import pytest
from asterion_remote.context_requirements import make_record,reconcile

def repo(tmp_path):
    root=tmp_path/"canon";root.mkdir(parents=True)
    docs=root/"docs";docs.mkdir()
    (docs/"v6.md").write_text(
        "V6 approval: preserve Control, Nexus and signed WSS.\n"
        "Never claim a release before actual Samsung acceptance.\n"
        "Owner corrected the model ceiling: 3B is a diagnostic only.\n"
        "Owner requests no redundant TeraBox credential bridge.\n",
        encoding="utf8")
    return root

def record(root,num,ident,topic,**kw):
    return make_record(root,"docs/v6.md",num,num,ident,topic,**kw)

def test_all_mandatory_evidence_preserved_across_bounded_partitions(tmp_path):
    root=repo(tmp_path)
    rows=[record(root,1,"control-wss","infra"),
          record(root,2,"release-hold","release"),
          record(root,3,"no-size-ceiling","model"),
          record(root,4,"terabox-ownership","storage")]
    answer=reconcile(root,rows,max_pack_chars=512)
    assert answer["mandatory_count"]==4
    assert len(answer["partitions"])>=2
    assert answer["requires_cross_partition_reasoning"]
    assert set(answer["mandatory_ids"])=={r["id"] for r in rows}
    assert answer["original_source_spans_verified"]
    assert not answer["all_requirements_certified"]

def test_supersession_preserves_full_history_and_owner_authority(tmp_path):
    root=repo(tmp_path)
    first=record(root,1,"previous-owner-req","inference",status="superseded")
    latest=record(root,3,"later-owner-req","inference",supersedes=["previous-owner-req"])
    result=reconcile(root,[first,latest])
    assert result["mandatory_ids"]==["later-owner-req"]
    assert len(result["partitions"])==1

def test_unresolved_conflicting_decisions_are_not_silently_resolved(tmp_path):
    root=repo(tmp_path)
    rows=[record(root,1,"option-a","same-decision"),
          record(root,2,"option-b","same-decision"),
          record(root,3,"unanswered","pending-decision",status="open")]
    answer=reconcile(root,rows)
    assert answer["potential_conflicts"]["same-decision"]==["option-a","option-b"]
    assert answer["unresolved_ids"]==["unanswered"]

def test_changed_source_and_invalid_supersession_fail_closed(tmp_path):
    root=repo(tmp_path)
    old=record(root,1,"known-source","infra")
    (root/"docs/v6.md").write_text("A new replacement requirement.\n")
    with pytest.raises(ValueError,match="canonical_source_changed"):
        reconcile(root,[old])
    root=repo(tmp_path/"new")
    a=record(root,1,"approved-source","infra",supersedes=["unknown-source"])
    with pytest.raises(ValueError,match="supersession_target_not_present"):
        reconcile(root,[a])
    x=record(root,1,"cycle-first","infra",status="superseded",
             supersedes=["cycle-second"])
    y=record(root,2,"cycle-second","infra",status="superseded",
             supersedes=["cycle-first"])
    with pytest.raises(ValueError,match="supersession_cycle"):
        reconcile(root,[x,y])

def test_reject_external_symlinks_and_no_unverified_source(tmp_path):
    root=repo(tmp_path)
    outside=tmp_path/"external.md"
    outside.write_text("secret unrelated data\n")
    (root/"docs/untrusted.md").symlink_to(outside)
    with pytest.raises(ValueError,match="external_source"):
        make_record(root,"docs/untrusted.md",1,1,"untrusted","external")
