"""Exact, source-linked Asterion requirements reconciliation for M4 cognition.

Pure evidence-pack engine layered over the existing canonical Git repositories.
Does not create a second memory DB, mutate source files, ask a model to retrieve
context, or pretend source-scale retrieval is native million-token inference.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re

IDENT=re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{2,90}$")
DIGEST=re.compile(r"^[a-f0-9]{64}$")
STATUSES={"active","superseded","open","proposed","rejected"}
KINDS={"requirement","decision","correction","evidence","constraint"}
IMPORTANCE={"mandatory","supporting"}
MAX_SOURCE=10*1024*1024

def _digest(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def _verify_record(root:Path,item:dict)->dict:
    required={"id","kind","status","importance","path","sha256",
              "start_line","end_line","span_sha256","topic","supersedes"}
    if not isinstance(item,dict) or set(item)!=required:
        raise ValueError("invalid_requirement_record_fields")
    if (not isinstance(item["id"],str) or not IDENT.fullmatch(item["id"]) or
        item["status"] not in STATUSES or item["kind"] not in KINDS or
        item["importance"] not in IMPORTANCE or
        not isinstance(item["topic"],str) or
        not IDENT.fullmatch(item["topic"])):
        raise ValueError("invalid_requirement_identity")
    rel=Path(item["path"])
    if (rel.is_absolute() or ".." in rel.parts or
        not rel.parts or not isinstance(item["path"],str) or
        "\\" in item["path"] or item["path"].startswith(".")):
        raise ValueError("invalid_source_path")
    path=(root/rel)
    if path.is_symlink() or not path.is_file() or root not in path.resolve().parents:
        raise ValueError("source_not_inside_authorized_project")
    if path.stat().st_size>MAX_SOURCE:
        raise ValueError("source_requires_external_chunk_index")
    if not DIGEST.fullmatch(item["sha256"]) or not DIGEST.fullmatch(item["span_sha256"]):
        raise ValueError("missing_immutable_source_hash")
    data=path.read_bytes()
    if _digest(data)!=item["sha256"]:
        raise ValueError("canonical_source_changed_reindex_required")
    if not type(item["start_line"]) is int or not type(item["end_line"]) is int:
        raise ValueError("invalid_source_line_range")
    lines=data.decode("utf-8").splitlines(keepends=True)
    first,last=item["start_line"],item["end_line"]
    if first<1 or last<first or last>len(lines):
        raise ValueError("source_span_out_of_bounds")
    span="".join(lines[first-1:last])
    if _digest(span.encode("utf-8"))!=item["span_sha256"]:
        raise ValueError("source_span_changed")
    deps=item["supersedes"]
    if not isinstance(deps,list) or len(set(deps))!=len(deps) or any(
            not isinstance(x,str) or not IDENT.fullmatch(x) for x in deps):
        raise ValueError("invalid_supersession_links")
    return {**item,"text":span}

def reconcile(root:str|Path,records:list[dict],*,max_pack_chars:int=12000)->dict:
    """Partition all mandatory records; preserve open/conflicting status explicitly.

    Returns *all* source-verified evidence, never a lossy summary.
    """
    root=Path(root).resolve(strict=True)
    if not 512<=max_pack_chars<=200000:
        raise ValueError("invalid_context_partition_size")
    if not isinstance(records,list) or not records or len(records)>100000:
        raise ValueError("nonempty_bounded_requirements_manifest_required")
    verified=[_verify_record(root,r) for r in records]
    ids={}
    for row in verified:
        if row["id"] in ids: raise ValueError("duplicate_requirement_id")
        ids[row["id"]]=row
    for row in verified:
        for old in row["supersedes"]:
            if old not in ids:raise ValueError("supersession_target_not_present")
            if old==row["id"]:raise ValueError("self_supersession")
    def visit(id,stack,done):
        if id in stack:raise ValueError("supersession_cycle")
        if id in done:return
        stack.add(id)
        for prior in ids[id]["supersedes"]:visit(prior,stack,done)
        stack.remove(id)
        done.add(id)
    done=set()
    for key in ids:visit(key,set(),done)
    replacements={key:[] for key in ids}
    for row in verified:
        for prev in row["supersedes"]:
            replacements[prev].append(row["id"])
    for row in verified:
        if row["status"]=="superseded" and not replacements[row["id"]]:
            raise ValueError("superseded_requirement_without_replacement")
        if row["status"]=="active" and replacements[row["id"]]:
            raise ValueError("active_requirement_has_explicit_successor")
    topic_active={}
    for row in verified:
        if row["status"]=="active":
            topic_active.setdefault(row["topic"],[]).append(row["id"])
    # Multiple active records for the same decision topic are *potential*
    # conflicts, never silently reduced to one. A larger evidence resolver
    # must inspect their precise semantic relationship.
    conflicts={topic:values for topic,values in topic_active.items()
               if len(values)>1}
    required=[r for r in verified if r["importance"]=="mandatory" and
              r["status"] in {"active","open"}]
    packages=[];current=[];size=0
    for row in required:
        text=json.dumps(row,sort_keys=True,ensure_ascii=False)
        if len(text)>max_pack_chars:
            raise ValueError("source_evidence_exceeds_single_partition")
        if current and size+len(text)>max_pack_chars:
            packages.append(current);current=[];size=0
        current.append(row);size+=len(text)
    if current:packages.append(current)
    if not packages:raise ValueError("no_active_mandatory_evidence")
    included={r["id"] for p in packages for r in p}
    if included != {r["id"] for r in required}:
        raise RuntimeError("mandatory_evidence_lost_in_context_partitioning")
    manifest_sha=_digest(json.dumps(records,sort_keys=True,
        ensure_ascii=False,separators=(",",":")).encode("utf-8"))
    return {"schema":"asterion.control.cognition.evidence/1",
        "manifest_sha256":manifest_sha,
        "mandatory_ids":sorted(included),
        "mandatory_count":len(included),"partitions":packages,
        "unresolved_ids":[r["id"] for r in verified if r["status"]=="open"],
        "potential_conflicts":conflicts,
        "requires_cross_partition_reasoning":len(packages)>1,
        "original_source_spans_verified":True,
        "native_context_is_unbounded":False,
        "all_requirements_certified":False}

def make_record(root,path,start_line,end_line,ident,topic,*,status="active",
                kind="requirement",importance="mandatory",supersedes=None):
    """Audited import helper: hashes exact unmodified canonical passages."""
    canonical=Path(root).resolve(strict=True)
    target=(canonical/path).resolve(strict=True)
    if canonical not in target.parents:raise ValueError("external_source")
    data=target.read_bytes()
    lines=data.decode("utf-8").splitlines(keepends=True)
    if start_line<1 or end_line<start_line or end_line>len(lines):
        raise ValueError("invalid_lines")
    return {"id":ident,"kind":kind,"status":status,"importance":importance,
      "path":path,"sha256":_digest(data),"start_line":start_line,
      "end_line":end_line,
      "span_sha256":_digest("".join(lines[start_line-1:end_line]).encode("utf-8")),
      "topic":topic,"supersedes":supersedes or []}
