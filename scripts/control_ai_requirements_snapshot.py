"""Exact-source Control AI requirements index, using existing cognition evidence engine.

The index never rewrites approved decisions or creates another memory DB.
Every imported passage is pinned to its original Git blob and SHA-256 hash.
Unrecognized edits fail before context assembly; no model-generated summary is
treated as a substitute for a canonical source.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from asterion_remote.context_requirements import make_record,reconcile

BLOB=re.compile(r"^[a-f0-9]{40}$")
_IDENT=re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{2,90}$")
SCHEMA="asterion.control.requirement-anchors/1"


def git_blob_sha(data:bytes)->str:
    """Git SHA-1 blob identifier; SHA-256 is separately verified per passage."""
    return hashlib.sha1(b"blob "+str(len(data)).encode("ascii")+b"\0"+data).hexdigest()


def _source(root:Path,entry:dict)->list[str]:
    if set(entry)!={"path","blob_sha"}:
        raise ValueError("invalid_index_source_metadata")
    relative=entry["path"]
    if not isinstance(relative,str) or "\\" in relative:
        raise ValueError("invalid_index_source_path")
    path=Path(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts or path.suffix!=".md":
        raise ValueError("invalid_index_source_path")
    resolved=(root/path)
    if (resolved.is_symlink() or not resolved.is_file() or
        root not in resolved.resolve().parents):
        raise ValueError("canonical_source_missing_or_external")
    if not isinstance(entry["blob_sha"],str) or not BLOB.fullmatch(entry["blob_sha"]):
        raise ValueError("source_git_blob_required")
    data=resolved.read_bytes()
    if git_blob_sha(data)!=entry["blob_sha"]:
        raise ValueError("pinned_canonical_source_changed")
    try:return data.decode("utf-8").splitlines(keepends=True)
    except UnicodeDecodeError as exc:
        raise ValueError("canonical_source_not_utf8") from exc


def _unique_line(lines:list[str],needle:str)->int:
    if not isinstance(needle,str) or len(needle)<8 or len(needle)>300:
        raise ValueError("index_anchor_invalid")
    matches=[n+1 for n,line in enumerate(lines) if needle in line]
    if len(matches)!=1:
        raise ValueError("exact_source_anchor_missing_or_ambiguous")
    return matches[0]


def snapshot(root:Path,index:dict,*,max_pack_chars:int=12000)->dict:
    root=Path(root).resolve(strict=True)
    if not isinstance(index,dict) or index.get("schema_version")!=SCHEMA:
        raise ValueError("unknown_requirements_index_schema")
    sources=index.get("files")
    descriptions=index.get("records")
    required=index.get("required_topics")
    if not isinstance(sources,dict) or not 1<=len(sources)<=100:
        raise ValueError("empty_or_oversized_source_index")
    if not isinstance(descriptions,list) or not 1<=len(descriptions)<=100000:
        raise ValueError("empty_or_oversized_requirements_index")
    if not isinstance(required,list) or not required or len(set(required))!=len(required):
        raise ValueError("invalid_required_topic_coverage")
    prepared={name:_source(root,value) for name,value in sources.items()}
    records=[]
    topics=set()
    for item in descriptions:
        required_fields={"id","file","start_match","end_before","topic",
                         "kind","status","importance","supersedes"}
        if (not isinstance(item,dict) or
                not required_fields <= set(item) or
                not set(item) <= required_fields|{"end_at_eof"} or
                ("end_at_eof" in item and type(item["end_at_eof"]) is not bool)):
            raise ValueError("invalid_requirement_anchor_fields")
        source=item["file"]
        if source not in prepared:
            raise ValueError("requirements_source_not_pinned")
        lines=prepared[source]
        first=_unique_line(lines,item["start_match"])
        next_anchor=item["end_before"]
        last=(_unique_line(lines,next_anchor)-1
              if next_anchor is not None else
              len(lines) if item.get("end_at_eof") else first)
        # Multi-line sections keep the complete original text, including
        # the requirement's explanatory and acceptance paragraphs.
        if last<first:
            raise ValueError("requirements_section_order_invalid")
        reference=sources[source]["path"]
        records.append(make_record(root,reference,first,last,item["id"],
            item["topic"],kind=item["kind"],status=item["status"],
            importance=item["importance"],supersedes=item["supersedes"]))
        topics.add(item["topic"])
    if not set(required)<=topics:
        raise ValueError("mandatory_owner_requirement_coverage_missing")
    result=reconcile(root,records,max_pack_chars=max_pack_chars)
    if result["mandatory_count"]!=len([x for x in records
            if x["importance"]=="mandatory" and x["status"] in {"active","open"}]):
        raise RuntimeError("mandatory_requirements_lost")
    result.update({
        "index_schema":SCHEMA,
        "source_count":len(sources),
        "indexed_records":len(records),
        "owner_topic_coverage":sorted(topics),
        "model_selected":False,
        "device_accepted":False,
        "all_v3_v6_approved_scope_covered":False,
        "original_sources_unchanged":True,
        "research_proposals_are_owner_approval":False
    })
    return result


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",type=Path,default=ROOT)
    parser.add_argument("--index",default="docs/CONTROL_AI_REQUIREMENT_ANCHORS_20261126.json")
    parser.add_argument("--max-pack-chars",type=int,default=12000)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args(argv)
    root=args.root.resolve(strict=True)
    index_file=(root/args.index)
    if index_file.is_symlink() or not index_file.is_file() or root not in index_file.resolve().parents:
        raise ValueError("invalid_owner_index_path")
    index=json.loads(index_file.read_text(encoding="utf-8"))
    outcome=snapshot(root,index,max_pack_chars=args.max_pack_chars)
    raw=json.dumps(outcome,indent=2,sort_keys=True,ensure_ascii=False)+"\n"
    if args.output is not None:
        destination=args.output.resolve()
        if root==destination or root in destination.parents:
            raise ValueError("do_not_overwrite_owner_repository_with_generated_evidence")
        if destination.exists():
            raise ValueError("requirement_snapshot_already_exists")
        destination.parent.mkdir(parents=True,exist_ok=True)
        with destination.open("x",encoding="utf-8") as file:
            file.write(raw);file.flush();os.fsync(file.fileno())
    print(json.dumps({"manifest_sha256":outcome["manifest_sha256"],
        "mandatory_count":outcome["mandatory_count"],
        "unresolved_ids":outcome["unresolved_ids"],
        "potential_conflicts":outcome["potential_conflicts"],
        "original_source_spans_verified":outcome["original_source_spans_verified"],
        "sources":outcome["source_count"],
        "partitions":len(outcome["partitions"]),
        "device_accepted":False},sort_keys=True))


if __name__=="__main__":
    main()
