"""Restore the verified 76 SFT + 2 DPO update descendant; no checkpoint pickle."""
from pathlib import Path
import argparse
import json
import zipfile
import shutil
from scripts.control_ai_adaptation import file_hash
from scripts.control_ai_native_adapter_export import canonical_paths,verified_file
from scripts.control_ai_retained_candidate import stage,REVISION
from scripts.control_ai_preferred_candidate import MANIFEST_SHA as PARENT_MANIFEST,WEIGHTS_SHA as PARENT_WEIGHTS,ADAPTER_SHA as PARENT_ADAPTER

ARTIFACT_ID=15246313817
ARCHIVE_SHA="927bca9757373dc8a01a4d8011cb4a165637da66d22fa61e83799d3805bf1f2d"
MANIFEST_SHA="f52d42297d6a8b2377c4139d46c0542c3f3e2eafd0dcb932ebb4f314c8fdc3bb"
ADAPTER_SHA="6067d116ff26a13abaf3cda618a760c0eea1cde74f065f03a5fec17bb8feee45"
WEIGHTS_SHA="cd7ab9dbe42ee8cea684171a1ad77c1253fa222dddf700733d88d31dda314473"

def restore(archive,root):
    archive,root=Path(archive),Path(root)
    if file_hash(archive)!=ARCHIVE_SHA:raise ValueError("applied_archive_digest_mismatch")
    root.mkdir(parents=True,exist_ok=False)
    candidate=root/"candidate";candidate.mkdir()
    with zipfile.ZipFile(archive) as source:
        if len(set(source.namelist()))!=len(source.namelist()):raise ValueError("duplicate_archive_member")
        (candidate/"candidate.json").write_bytes(source.read("next-candidate/candidate.json"))
        if file_hash(candidate/"candidate.json")!=MANIFEST_SHA:raise ValueError("applied_manifest_digest_mismatch")
        manifest=json.loads((candidate/"candidate.json").read_text())
        parent=manifest.get("parent_adapter",{})
        metrics=manifest.get("training_metrics",{})
        if (manifest.get("base_revision_declared")!=REVISION or manifest.get("weights_changed") is not True
            or manifest.get("trainable_sha256_before")!=PARENT_WEIGHTS or manifest.get("trainable_sha256_after")!=WEIGHTS_SHA
            or parent.get("parent_candidate_manifest_sha256")!=PARENT_MANIFEST
            or parent.get("peft_adapter_sha256")!=PARENT_ADAPTER
            or manifest.get("training_arguments",{}).get("max_steps")!=40 or metrics.get("epoch")!=1.0):
            raise ValueError("applied_training_lineage_mismatch")
        files=canonical_paths(manifest["artifact_sha256"])
        if files.get("adapter/adapter_model.safetensors")!=ADAPTER_SHA:raise ValueError("applied_adapter_identity_mismatch")
        for name,digest in files.items():
            if not name.startswith("adapter/"):raise ValueError("unexpected_candidate_member")
            member=source.getinfo("next-candidate/"+name)
            if member.file_size>64*1024*1024:raise ValueError("candidate_member_too_large")
            target=candidate/name;target.parent.mkdir(parents=True,exist_ok=True)
            with target.open("xb") as output,source.open(member) as input_:
                shutil.copyfileobj(input_,output)
            verified_file(candidate,name,digest)
        applied=root/"applied";applied.mkdir()
        for name in ("train.jsonl","holdout.jsonl","manifest.json"):
            (applied/name).write_bytes(source.read("applied-v3/"+name))
    return candidate

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("archive",type=Path);p.add_argument("root",type=Path)
    p.add_argument("--weights",action="store_true")
    args=p.parse_args()
    restore(args.archive,args.root)
    stage(args.root,args.weights,archive_sha=ARCHIVE_SHA,artifact_id=ARTIFACT_ID)
