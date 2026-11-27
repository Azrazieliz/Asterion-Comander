"""Reproducible public Model Lab fixtures for evidence-based decisions and general replay.

Targets are computed by the operations below. They are training/validation fixtures,
never real device receipts, private project histories or human quality reviews.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def record(family, index, domain, instruction, result):
    return {
        "id": f"{family}-{index:02d}", "domain": domain, "workflow_family": family,
        "rights_verified": True, "target_origin": "original_executable_fixture",
        "source": f"scripts/control_ai_evidence_corpus.py#{family}",
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "messages": [{"role": "user", "content": instruction},
                     {"role": "assistant", "content": str(result)}],
    }


def build():
    train, validation, evaluation, preferences = [], [], [], []
    for i in range(12):
        expected = f"release-record-{i}"
        observed = expected if i % 3 == 0 else None if i % 3 == 1 else expected + "-old"
        src = sha(expected)[:16]
        dst = sha(observed)[:16] if observed is not None else "unobserved"
        verdict = "unknown" if observed is None else "verified" if src == dst else "failed"
        prompt = (f"Export {i} was acknowledged. Reference digest prefix {src}; independent "
                  f"destination digest prefix {dst}. Classify integrity. Reply only verified, failed or unknown.")
        row = record("export-integrity", i, "artifacts", prompt, verdict)
        train.append(row)
        if i < 6:
            preferences.append({"prompt": row["messages"][:-1], "chosen": verdict,
                                "rejected": "failed" if verdict == "verified" else "verified",
                                **{k: row[k] for k in ("source", "source_sha256", "workflow_family", "rights_verified", "target_origin")}})

        expected_cap = f"read.table.{i}"
        actual = [f"read.text.{i}", expected_cap if i % 2 else f"read.plot.{i}"]
        train.append(record("signed-inventory", i, "cross_app",
            f"A signed provider advertises {', '.join(actual)}. Is {expected_cap} advertised? Answer yes or no.",
            "yes" if expected_cap in actual else "no"))

        total, size = 11 + i * 3, 3 + i % 4
        train.append(record("page-count", i, "reasoning",
            f"Fit {total} records into pages of capacity {size}. Return only the minimum number of pages.",
            (total + size - 1) // size))
        values = [i, 2 * i + 1, 3 * i + 4, i + 9]
        train.append(record("python-slice", i, "coding",
            f"What integer is printed by Python: print({values}[1:3][-1])? Give only the integer.",
            values[1:3][-1]))

    # Different mechanisms and source families. The trainer gets validation
    # identity/contamination checks only; the free-generation suite is separate.
    for i in range(6):
        received, required = 80 + i, 80 + i + (i % 2)
        validation.append(record("sample-count", i, "diagnostics",
            f"Observation {i}: exactly {required} samples are required and the counter reads {received}. "
            "Is the count complete? Answer yes or no.", "yes" if received == required else "no"))
        validation.append(record("distance", i, "education",
            f"A cart travels {4+i} metres per second for {7+i} seconds. Return its distance as an integer in metres.",
            (4 + i) * (7 + i)))

    for i in range(6):
        expected = [f"case-{i}-a", f"case-{i}-b"]
        passed = set(expected[:i % 3])
        failed = {expected[-1]} if i % 3 == 1 else set()
        verdict = "failed" if failed else "verified" if passed == set(expected) else "unknown"
        row = record("test-postconditions", i, "diagnostics",
            f"Release check {100+i} requires passes for both {expected}. Observed passes: {sorted(passed)}. "
            f"Observed failures: {sorted(failed)}. No other outcomes have been observed. "
            "Classify this release check. Output only verified, failed or unknown.", verdict)
        evaluation.append(row)

        current = f"note-{i}:B" if i % 2 == 0 else f"note-{i}:A"
        replacement = "owner-approved correction" if i % 2 == 0 else "draft suggestion"
        evaluation.append(record("decision-authority", i, "memory",
            f"An accepted entry is note-{i}:A. Later, a {replacement} names note-{i}:B. "
            "Only an approved correction supersedes an accepted entry. Return the authoritative identifier alone.",
            current))
        price, n = 7 + i, 2 + i
        evaluation.append(record("french-unit-cost", i, "reasoning",
            f"{n} carnets coûtent {n*price} euros au total. Quel est le prix d’un carnet ? Réponds uniquement par le nombre.",
            price))
        items = [i, i+4, i, i+1]
        evaluation.append(record("distinct-count", i, "coding",
            f"In Python, what integer is len(set({items}))? Output the integer only.", len(set(items))))
    return train, validation, evaluation, preferences


def write_jsonl(path, rows):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write(destination):
    train, validation, evaluation, preferences = build()
    groups = [{r["workflow_family"] for r in rows} for rows in (train, validation, evaluation)]
    if any(a & b for i, a in enumerate(groups) for b in groups[i+1:]):
        raise ValueError("cross_split_workflow_family")
    prompts = [r["messages"][-2]["content"].strip().casefold() for rows in (train, validation, evaluation) for r in rows]
    if len(set(prompts)) != len(prompts):
        raise ValueError("cross_split_or_within_split_duplicate")
    destination.mkdir(parents=True, exist_ok=False)
    for filename, rows in (("train", train), ("validation", validation), ("preferences", preferences)):
        write_jsonl(destination / (filename + ".jsonl"), rows)
    write_jsonl(destination / "evaluation.jsonl", [
        {"id": row["id"], "split": "holdout", "category": row["workflow_family"], "mode": "exact",
         "prompt": row["messages"][0]["content"], "expected": row["messages"][1]["content"],
         "source": row["source"], "source_sha256": row["source_sha256"]} for row in evaluation])


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("output", type=Path)
    write(cli.parse_args().output)
