"""Project the existing verified requirements snapshot into a signed Android asset."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.control_ai_requirements_snapshot import snapshot


def asset(root):
    index = json.loads((root / "docs/CONTROL_AI_REQUIREMENT_ANCHORS_20261126.json").read_text(encoding="utf-8"))
    result = snapshot(root, index)
    return {
        "schema": "asterion.control.android-requirements/1",
        "index_sha256": result["canonical_index_sha256"],
        "unresolved_ids": result["unresolved_ids"],
        "potential_conflicts": result["potential_conflicts"],
        "records": [record for partition in result["partitions"] for record in partition],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    # A staged destination permits explicit diff and review before replacing a signed asset.
    with args.output.open("x", encoding="utf-8", newline="\n") as file:
        json.dump(asset(ROOT), file, ensure_ascii=False, indent=2)
        file.write("\n")
