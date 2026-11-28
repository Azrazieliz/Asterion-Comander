"""Restore the verified 36-total-step descendant; never replay optimizer pickle."""
from pathlib import Path
import argparse
import json
import zipfile
import shutil
from scripts.control_ai_adaptation import file_hash
from scripts.control_ai_native_adapter_export import canonical_paths,verified_file
from scripts.control_ai_retained_candidate import stage,REVISION

ARTIFACT_ID=15240659652
ARCHIVE_SHA="6cc57eaa2f42ff0bcdebb375d98e3ddb726c0299ccbbb06ce8bad6aad412c408"
MANIFEST_SHA="2c6483987ea47b449b0a81e95dfc03a6244069ef5241a811f316508d9806097d"
ADAPTER_SHA="b44c83478762c6fa70041a7313755aabcefc0408207ec64eb64abaf948da8039"
PARENT_SHA="188e6e407b9c9343a092d3ac291f42e946f05e8b0ddcef93bdb521c2abe02b5f"
WEIGHTS_SHA="7026ede020e53ee9a214f43576066542f5af07988f60a4806ab8e90bfdbd7772"

def restore(archive,root):
    archive,root=Path(archive),Path(root)
    if file_hash(archive)!=ARCHIVE_SHA:raise ValueError("continued_archive_digest_mismatch")
    root.mkdir(parents=True,exist_ok=False)
    candidate=root/"candidate";candidate.mkdir()
    with zipfile.ZipFile(archive) as source:
        if len(set(source.namelist()))!=len(source.namelist()):raise ValueError("duplicate_archive_member")
        (candidate/"candidate.json").write_bytes(source.read("continued/candidate.json"))
        if file_hash(candidate/"candidate.json")!=MANIFEST_SHA:raise ValueError("continued_manifest_digest_mismatch")
        manifest=json.loads((candidate/"candidate.json").read_text())
        if (manifest.get("base_revision_declared")!=REVISION or manifest.get("weights_changed") is not True
            or manifest.get("trainable_sha256_before")!=PARENT_SHA or manifest.get("trainable_sha256_after")!=WEIGHTS_SHA
            or manifest.get("training_arguments",{}).get("max_steps")!=24
            or manifest.get("training_metrics",{}).get("epoch")!=1.0):
            raise ValueError("continued_training_lineage_mismatch")
        files=canonical_paths(manifest["artifact_sha256"])
        if files.get("adapter/adapter_model.safetensors")!=ADAPTER_SHA:raise ValueError("continued_adapter_identity_mismatch")
        for name,digest in files.items():
            if not name.startswith("adapter/"):raise ValueError("unexpected_candidate_member")
            member=source.getinfo("continued/"+name)
            if member.file_size>64*1024*1024:raise ValueError("candidate_member_too_large")
            target=candidate/name;target.parent.mkdir(parents=True,exist_ok=True)
            with target.open("xb") as output,source.open(member) as input_:
                shutil.copyfileobj(input_,output)
            verified_file(candidate,name,digest)
        applied=root/"applied";applied.mkdir()
        for name in ("train.jsonl","holdout.jsonl","preferences.jsonl","manifest.json"):
            (applied/name).write_bytes(source.read("applied/"+name))
    return candidate

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("archive",type=Path);p.add_argument("root",type=Path)
    p.add_argument("--weights",action="store_true")
    args=p.parse_args()
    restore(args.archive,args.root)
    stage(args.root,args.weights,archive_sha=ARCHIVE_SHA,artifact_id=ARTIFACT_ID)
