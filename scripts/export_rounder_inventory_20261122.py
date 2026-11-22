#!/usr/bin/env python3
"""Collect an owner-approved Rounder TeraBox subtree through existing Control.

This is a CLIENT of the installed Control app, not a second phone controller.
Uses existing paired native WSS/LAN adapter and the already-present signed
AppBridge protocol. Only JSON/CSV metadata leaves Rounder; media is never read.

Before use: in Rounder, choose a TeraBox folder and approve 30-minute inventory
access; in Control, locally approve Rounder under app integrations.
Run from the original Asterion Control Windows Python environment:
  python scripts/export_rounder_inventory_20261122.py --format both

The export stays on the owner's PC, not in GitHub or ChatGPT messages.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from asterion_remote.phone_bridge import request

PACKAGE = "com.openlocal.office"
APPROVAL_HINT = (
    "Approve Rounder in Control > Asterion app integrations > Manage app access; "
    "then in Rounder select a TeraBox folder > Allow Control inventory (30 min)."
)
FIELDS = ("path", "parent", "name", "type", "folder", "size", "modified", "md5")


class ExportError(RuntimeError):
    pass


def inner(response: dict) -> tuple[str, dict]:
    """Unwrap existing Control AppBridge's real dual-receipt, fail closed."""
    if not isinstance(response, dict):
        raise ExportError("Control did not return a structured receipt")
    if not response.get("ok", False):
        raise ExportError(
            "Control rejected inventory: "
            + str(response.get("reason") or response.get("status") or response.get("result"))
            + ". " + APPROVAL_HINT
        )
    partner = response.get("result")
    if not isinstance(partner, dict) or not partner.get("ok", False):
        raise ExportError("Rounder partner did not confirm authorization: " + APPROVAL_HINT)
    body = partner.get("result")
    if not isinstance(body, dict):
        raise ExportError("Invalid signed Rounder result")
    status = partner.get("status", body.get("status", "unknown"))
    return status, body


def call(action: str, payload: dict | None = None) -> tuple[str, dict, str]:
    receipt_id = "rounder-export-" + uuid.uuid4().hex
    body = {
        "package": PACKAGE, "action": action,
        "request_id": receipt_id, "payload": payload or {},
    }
    # Never automatically replay an uncertain POST, including a read-only one.
    try:
        result = request("/app-bridge/invoke", "POST", body, timeout=11.0).json()
    except Exception as exc:
        # An uncertain WSS/Binder acknowledgement is not permission to repeat
        # the invoke. Read the SAME signed/idempotent request's status instead.
        # This also recovers replies delayed after a transient 7-second call
        # timeout without starting another TeraBox metadata operation.
        try:
            status, response = status_for(receipt_id)
            return status, response, receipt_id
        except ExportError as status_error:
            raise ExportError(
                "Inventory action outcome uncertain; original receipt "
                + receipt_id + ", status lookup failed: "
                + str(status_error)[:180]
            ) from exc
    status, response = inner(result)
    return status, response, receipt_id


def status_for(receipt_id: str) -> tuple[str, dict]:
    # Existing operation call only queries the prior request: never invokes anew.
    try:
        response = request(
            "/app-bridge/operation", "POST",
            {"package": PACKAGE, "request_id": receipt_id, "cancel": False},
            timeout=10.0,
        ).json()
    except Exception as exc:
        raise ExportError(
            "Operation status unknown; original receipt remains " + receipt_id
        ) from exc
    return inner(response)


def wait_for_inventory(max_wait: float, interval: float) -> dict:
    state, meta, receipt = call("rounder.inventory.meta")
    start = time.monotonic()

    def retryable_index_error() -> bool:
        # A TeraBox DNS outage can leave the existing pending-page index marked
        # failed even after connectivity returns. Status queries trigger the
        # signed Rounder provider's resumable selected-subtree retry.
        if state != "failed" or meta.get("reason") != "index_error":
            return False
        detail = str(meta.get("index_error", "")).lower()
        return bool(meta.get("index_building")) and any(
            marker in detail for marker in (
                "unable to resolve host", "unknownhostexception",
                "temporary failure in name resolution",
                "no address associated with hostname",
            )
        )

    while state == "accepted" or retryable_index_error():
        if time.monotonic() - start >= max_wait:
            detail = str(meta.get("index_error") or meta.get("reason") or state)
            raise ExportError(
                "Selected-folder inventory not yet complete (bounded retry): "
                + detail[:180] + "; receipt " + receipt
            )
        time.sleep(interval)
        state, meta = status_for(receipt)
    if state != "completed" or not meta.get("complete_for_index_generation"):
        raise ExportError("Index is not complete: " + str(meta.get("index_error") or meta.get("reason", state)))
    if not isinstance(meta.get("generation"), int) or meta["generation"] < 1:
        raise ExportError("Index generation missing")
    if not str(meta.get("root", "")).startswith("/"):
        raise ExportError("Approved directory missing")
    if not re.fullmatch(r"[0-9a-f]{24}", str(meta.get("account_fingerprint", ""))):
        raise ExportError("Account identity fingerprint missing")
    return meta


def default_directory() -> Path:
    # Original PC's C: is space constrained. Prefer D: without altering files.
    drive = Path("D:/")
    if os.name == "nt" and drive.exists():
        return drive / "AsterionControl" / "exports" / "rounder"
    return Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "AsterionControl" / "exports" / "rounder"


def safe_cell(value: object) -> str:
    text = "" if value is None else str(value)
    # Prevent spreadsheet formula evaluation without changing canonical JSON.
    if text.lstrip().startswith(("=", "+", "-", "@")) or text[:1] in ("\t", "\r", "\n"):
        return "'" + text
    return text


def write_checkpoint(path: Path, value: dict) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def collect(metadata: dict, directory: Path, formats: str, max_pages: int) -> dict:
    scope_root = metadata["root"]
    generation = metadata["generation"]
    account = metadata["account_fingerprint"]
    fingerprint = hashlib.sha256(
        (account + "|" + scope_root + "|" + str(generation)).encode("utf-8")
    ).hexdigest()[:20]
    directory.mkdir(parents=True, exist_ok=True)
    stem = directory / ("rounder-" + fingerprint)
    jsonl_part = Path(str(stem) + ".jsonl.part")
    csv_part = Path(str(stem) + ".csv.part")
    checkpoint = Path(str(stem) + ".checkpoint.json")
    final_json = Path(str(stem) + ".json")
    final_csv = Path(str(stem) + ".csv")
    done = False
    if checkpoint.exists():
        stored = json.loads(checkpoint.read_text(encoding="utf-8"))
        if (stored.get("root") != scope_root or
                stored.get("generation") != generation or
                stored.get("account_fingerprint") != account):
            raise ExportError("Checkpoint belongs to another root or index generation")
        if stored.get("done"):
            if not ((formats == "json" and final_json.is_file()) or
                    (formats == "csv" and final_csv.is_file()) or
                    (formats == "both" and final_json.is_file() and final_csv.is_file())):
                raise ExportError("A previous export completed but its final file is missing")
            return stored["summary"]
        if not jsonl_part.is_file() or not csv_part.is_file():
            raise ExportError("Checkpoint exists but one staging file is missing")
        # A crash after an append but before the checkpoint must not duplicate
        # entries on resume. Restore the last fully committed byte offsets.
        for file_path, key in ((jsonl_part, "jsonl_bytes"), (csv_part, "csv_bytes")):
            last = stored.get(key)
            if not isinstance(last, int) or last < 0 or file_path.stat().st_size < last:
                raise ExportError("Cannot safely resume an incomplete staging file")
            with file_path.open("r+b") as file_handle:
                file_handle.truncate(last)
        cursor = stored["after"]
        count = stored["entries"]
        pages = stored["pages"]
    else:
        if jsonl_part.exists() or csv_part.exists():
            raise ExportError("Unrecognized partial inventory exists; owner review required")
        jsonl_part.touch()
        with csv_part.open("w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow(FIELDS)
        cursor = ""
        count = 0
        pages = 0
        write_checkpoint(checkpoint, {"root": scope_root, "account_fingerprint": account,
                                      "generation": generation,
                                      "after": cursor, "entries": count, "pages": pages,
                                      "jsonl_bytes": jsonl_part.stat().st_size,
                                      "csv_bytes": csv_part.stat().st_size})
    while not done:
        if pages >= max_pages:
            raise ExportError("Stopped at requested page limit; checkpoint is resumable")
        state, response, receipt = call("rounder.inventory.page", {
            "generation": generation, "after": cursor, "format": "json",
        })
        if state != "completed":
            raise ExportError("Rounder page not complete; receipt " + receipt)
        if (response.get("generation") != generation or
            response.get("root") != scope_root or
            response.get("account_fingerprint") != account):
            raise ExportError("TeraBox account/root/generation changed during collection")
        items = response.get("items")
        if not isinstance(items, list) or response.get("count") != len(items):
            raise ExportError("Page count does not match verified entries")
        next_cursor = response.get("next_after")
        if not isinstance(next_cursor, str):
            raise ExportError("Missing page continuation cursor")
        if items and (next_cursor != items[-1].get("path") or next_cursor <= cursor):
            raise ExportError("Invalid or non-advancing cursor")
        if not items and response.get("has_more"):
            raise ExportError("Rounder returned a non-progressing page")
        # Validate before writing either representation.
        for item in items:
            if not isinstance(item, dict) or any(key not in item for key in FIELDS):
                raise ExportError("Incomplete inventory metadata row")
            path = item["path"]
            if not isinstance(path, str) or not path.startswith(
                "/" if scope_root == "/" else scope_root + "/"
            ):
                raise ExportError("Escaped granted TeraBox subtree")
        with jsonl_part.open("a", encoding="utf-8", newline="\n") as f:
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
            f.flush()
            os.fsync(f.fileno())
        with csv_part.open("a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            for item in items:
                writer.writerow([safe_cell(item[key]) for key in FIELDS])
            f.flush()
            os.fsync(f.fileno())
        count += len(items)
        pages += 1
        cursor = next_cursor
        done = not bool(response.get("has_more"))
        # Crash-safe resume requires committing both append logs before cursor.
        write_checkpoint(checkpoint, {"root": scope_root, "account_fingerprint": account,
                                      "generation": generation,
                                      "after": cursor, "entries": count, "pages": pages,
                                      "jsonl_bytes": jsonl_part.stat().st_size,
                                      "csv_bytes": csv_part.stat().st_size})
    expected = metadata.get("entries")
    if expected is not None and count != expected:
        raise ExportError(
            "File count does not match complete index: " + str(count) + " / " + str(expected)
        )
    if formats in ("both", "json"):
        tmp_json = Path(str(final_json) + ".tmp")
        with tmp_json.open("w", encoding="utf-8") as out:
            out.write('{"schema":"rounder-inventory-v1","root":')
            out.write(json.dumps(scope_root, ensure_ascii=False))
            out.write(',"generation":' + str(generation))
            out.write(',"account_fingerprint":' + json.dumps(account))
            out.write(',"entries":[')
            first = True
            with jsonl_part.open("r", encoding="utf-8") as source:
                for line in source:
                    if not line.strip():
                        continue
                    if not first:
                        out.write(",")
                    out.write(line.rstrip("\n"))
                    first = False
            out.write("]}\n")
            out.flush()
            os.fsync(out.fileno())
        tmp_json.replace(final_json)
    if formats in ("both", "csv"):
        csv_part.replace(final_csv)
    # Keep the JSONL as local verification evidence, but flag durable completion.
    summary = {
        "ok": True, "status": "complete", "source": "Rounder via Control",
        "root_sha256_prefix": hashlib.sha256(scope_root.encode("utf-8")).hexdigest()[:16],
        "account_fingerprint": account,
        "generation": generation, "entries": count, "pages": pages,
        "files": metadata.get("files"), "folders": metadata.get("folders"),
        "json_path": str(final_json) if formats in ("both", "json") else None,
        "csv_path": str(final_csv) if formats in ("both", "csv") else None,
        "private_local_export": True,
    }
    write_checkpoint(checkpoint, {"done": True, "root": scope_root,
        "account_fingerprint": account, "generation": generation, "summary": summary})
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("both", "json", "csv"), default="both")
    parser.add_argument("--directory", type=Path, default=None)
    parser.add_argument("--max-pages", type=int, default=100000)
    parser.add_argument("--index-wait", type=float, default=1800.0)
    parser.add_argument("--poll-interval", type=float, default=3.0)
    args = parser.parse_args()
    try:
        if args.max_pages < 1 or args.index_wait < 0 or args.poll_interval < 0.5:
            raise ExportError("Invalid bounded polling limits")
        metadata = wait_for_inventory(args.index_wait, args.poll_interval)
        summary = collect(metadata, args.directory or default_directory(),
                          args.format, args.max_pages)
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    except (ExportError, OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "status": "incomplete",
                          "error": str(exc)[:600]}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
