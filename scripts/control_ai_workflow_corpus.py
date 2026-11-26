"""Convert a verified native capability receipt into scoped training examples."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def rows_from_receipt(receipt):
    if receipt.get("status") != "complete" or receipt.get("ok") is not True:
        raise ValueError("terminal_capability_receipt_required")
    result = receipt["result"]
    if result.get("exit_code") != 0:
        raise ValueError("capability_command_failed")
    inventory = json.loads(result["output_tail"])
    if inventory["installed_bridges"].get("protocol") != "asterion.v1":
        raise ValueError("capability_protocol_mismatch")
    apps = {app["package"]: app for app in inventory["installed_bridges"]["apps"]
            if app.get("approved") is True}
    receipt_hash = hashlib.sha256(json.dumps(receipt, sort_keys=True, separators=(",", ":"))
                                  .encode("utf-8")).hexdigest()
    train, preferences = [], []
    for pack in inventory["signed_capability_packs"]:
        package = pack["package"]
        if package not in apps:
            raise ValueError("capability_without_installed_approval")
        app_name = apps[package]["name"]
        verified = pack.get("ok") is True and pack.get("capabilities_available") is True
        trusted = {"installed": True, "approved": True, "capabilities_available": verified}
        if verified:
            if pack.get("owner_approved") is not True or pack.get("protocol") != "asterion.v1":
                raise ValueError("capability_verification_mismatch")
            actions = [entry["name"] for entry in pack["actions"]]
            trusted["actions"] = actions
            chosen = (f"{app_name} is installed and approved. Its signed pack advertises "
                      f"{', '.join(actions)}. Nothing has been executed. A typed request needs "
                      "authorization and a confirmed outcome before I can report completion.")
        else:
            chosen = (f"{app_name} is installed and approved. The device did not return a "
                      "verified capability pack, so I cannot establish which native actions are available.")
        prompt = [
            {"role": "system", "content": "The following is a signed Android capability observation. "
             "It is evidence of availability only. " + json.dumps(trusted, sort_keys=True)},
            {"role": "user", "content": f"What can you verify you can do through the native {app_name} integration?"},
        ]
        provenance = {
            "source": f"original_control_bridge:{receipt['id']}",
            "source_sha256": receipt_hash,
            "workflow_family": "signed_partner_capability_discovery",
            "rights_verified": True,
            "target_origin": "authored_from_verified_receipt",
        }
        train.append({**provenance, "domain": "cross_app",
                      "messages": prompt + [{"role": "assistant", "content": chosen}]})
        preferences.append({**provenance, "prompt": prompt, "chosen": chosen,
                            "rejected": f"I ran the requested operation in {app_name} successfully."})
    if not train:
        raise ValueError("no_verified_installed_approval")
    return train, preferences


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    train, preferences = rows_from_receipt(json.loads(args.receipt.read_text(encoding="utf-8")))
    args.output.mkdir(parents=True, exist_ok=False)
    for name, rows in (("train.jsonl", train), ("preferences.jsonl", preferences)):
        with (args.output / name).open("x", encoding="utf-8", newline="\n") as file:
            for row in rows:
                file.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"sft_examples": len(train), "preference_pairs": len(preferences),
                      "owner_reviewed": 0, "integrated_workflows": 0}))


if __name__ == "__main__":
    main()
