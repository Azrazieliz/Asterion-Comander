"""Restore the verified 36 SFT + 2 DPO update descendant; no checkpoint pickle."""
from pathlib import Path
import argparse
import json
import zipfile
import shutil
from scripts.control_ai_adaptation import file_hash
from scripts.control_ai_native_adapter_export import canonical_paths,verified_file
from scripts.control_ai_retained_candidate import stage,REVISION
from scripts.control_ai_continued_candidate import MANIFEST_SHA as SFT_MANIFEST,WEIGHTS_SHA as SFT_WEIGHTS,ADAPTER_SHA as SFT_ADAPTER

ARTIFACT_ID=15243967683
ARCHIVE_SHA="b012bdf6c6f9e324c8167507cb32f6a8fd654d48182299a2ab98c9bff2128e3c"
MANIFEST_SHA="67807f4de850ddba8e0d7ce801badb39a5561f25f91e888481f3bc803fb7b925"
ADAPTER_SHA="143411c09a2e53551e1ddf76005e41b9eb32d5f3b8178134f99c020940fd793c"
WEIGHTS_SHA="149416a629f55a0681c72fc9d7ae3fd245b59fe2970be676229df32b7e81e256"

def restore(archive,root):
    archive,root=Path(archive),Path(root)
    if file_hash(archive)!=ARCHIVE_SHA:raise ValueError("preferred_archive_digest_mismatch")
    root.mkdir(parents=True,exist_ok=False)
    candidate=root/"candidate";candidate.mkdir()
    with zipfile.ZipFile(archive) as source:
        if len(set(source.namelist()))!=len(source.namelist()):raise ValueError("duplicate_archive_member")
        (candidate/"candidate.json").write_bytes(source.read("preferred/candidate.json"))
        if file_hash(candidate/"candidate.json")!=MANIFEST_SHA:raise ValueError("preferred_manifest_digest_mismatch")
        manifest=json.loads((candidate/"candidate.json").read_text())
        parent=manifest.get("parent_adapter",{})
        dpo=manifest.get("preference_training",{})
        if (manifest.get("base_revision_declared")!=REVISION or manifest.get("weights_changed") is not True
            or manifest.get("trainable_sha256_before")!=SFT_WEIGHTS or manifest.get("trainable_sha256_after")!=WEIGHTS_SHA
            or parent.get("parent_candidate_manifest_sha256")!=SFT_MANIFEST
            or parent.get("peft_adapter_sha256")!=SFT_ADAPTER
            or dpo.get("method")!="dpo" or dpo.get("steps")!=2 or dpo.get("sft_weights_sha256")!=SFT_WEIGHTS):
            raise ValueError("preferred_training_lineage_mismatch")
        files=canonical_paths(manifest["artifact_sha256"])
        if files.get("adapter/adapter_model.safetensors")!=ADAPTER_SHA:raise ValueError("preferred_adapter_identity_mismatch")
        for name,digest in files.items():
            if not name.startswith("adapter/"):raise ValueError("unexpected_candidate_member")
            member=source.getinfo("preferred/"+name)
            if member.file_size>64*1024*1024:raise ValueError("candidate_member_too_large")
            target=candidate/name;target.parent.mkdir(parents=True,exist_ok=True)
            with target.open("xb") as output,source.open(member) as input_:
                shutil.copyfileobj(input_,output)
            verified_file(candidate,name,digest)
        applied=root/"applied";applied.mkdir()
        for name in ("train.jsonl","holdout.jsonl","preferences.jsonl","manifest.json"):
            (applied/name).write_bytes(source.read("retained/applied/"+name))
    return candidate

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("archive",type=Path);p.add_argument("root",type=Path)
    p.add_argument("--weights",action="store_true")
    args=p.parse_args()
    restore(args.archive,args.root)
    stage(args.root,args.weights,archive_sha=ARCHIVE_SHA,artifact_id=ARTIFACT_ID)
