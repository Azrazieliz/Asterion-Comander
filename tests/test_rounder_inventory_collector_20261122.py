"""Regression for Control's existing WSS AppBridge Rounder inventory collector.

Uses a fake phone receipt transport; no network, user files or credentials.
"""
import csv
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "export_rounder_inventory_20261122.py"
fake_pkg = types.ModuleType("asterion_remote")
fake_pkg.__path__ = []
fake_phone = types.ModuleType("asterion_remote.phone_bridge")
fake_phone.request = lambda *args, **kwargs: None
sys.modules.setdefault("asterion_remote", fake_pkg)
sys.modules["asterion_remote.phone_bridge"] = fake_phone
spec = importlib.util.spec_from_file_location("rounder_inventory", SCRIPT)
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)


class Reply:
    def __init__(self, value):
        self.value = value

    def json(self):
        return self.value


def envelope(body):
    return {"ok": True, "status": body["status"],
            "result": {"ok": True, "status": body["status"], "result": body}}


class InventoryExportTest(unittest.TestCase):
    def setUp(self):
        self.root = "/Apps/Koikatsu"
        self.meta = {
            "status": "completed", "root": self.root, "generation": 7,
            "account_fingerprint": "d54c50b6ad0e2edcb1f2ade3",
            "complete_for_index_generation": True, "entries": 2,
            "files": 1, "folders": 1,
        }
        self.items = [
            {"path": self.root + "/Mods", "parent": self.root,
             "name": "Mods", "type": "folder", "folder": True,
             "size": 0, "modified": 0, "md5": None},
            {"path": self.root + '/Mods/日本語,mod.zip',
             "parent": self.root + "/Mods",
             "name": "日本語,mod.zip", "type": "archive", "folder": False,
             "size": 456, "modified": 171111, "md5": "a" * 32},
        ]
        self.cursors = []
        self.receipts = []

    def transport(self, route, method, payload, timeout):
        assert route == "/app-bridge/invoke"
        assert method == "POST"
        assert payload["package"] == "com.openlocal.office"
        self.receipts.append(payload["request_id"])
        if payload["action"] == "rounder.inventory.meta":
            return Reply(envelope(self.meta))
        self.assertEqual(payload["action"], "rounder.inventory.page")
        after = payload["payload"]["after"]
        self.cursors.append(after)
        if not after:
            return Reply(envelope({
                "status": "completed", "root": self.root,
                "generation": 7, "account_fingerprint": "d54c50b6ad0e2edcb1f2ade3", "items": [self.items[0]], "count": 1,
                "next_after": self.items[0]["path"], "has_more": True,
            }))
        return Reply(envelope({
            "status": "completed", "root": self.root,
            "generation": 7, "account_fingerprint": "d54c50b6ad0e2edcb1f2ade3", "items": [self.items[1]], "count": 1,
            "next_after": self.items[1]["path"], "has_more": False,
        }))

    def test_complete_json_and_csv_with_existing_control_route(self):
        with tempfile.TemporaryDirectory() as work:
            with patch.object(inventory, "request", side_effect=self.transport):
                meta = inventory.wait_for_inventory(5, 0.5)
                summary = inventory.collect(meta, Path(work), "both", 4)
            self.assertEqual(summary["status"], "complete")
            self.assertEqual(summary["entries"], 2)
            self.assertEqual(len(set(self.receipts)), 3)
            values = json.loads(Path(summary["json_path"]).read_text("utf-8"))
            self.assertEqual(values["entries"], self.items)
            with open(summary["csv_path"], newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[1]["name"], "日本語,mod.zip")

    def test_resume_after_page_boundary_without_duplicates(self):
        with tempfile.TemporaryDirectory() as work:
            with patch.object(inventory, "request", side_effect=self.transport):
                with self.assertRaisesRegex(inventory.ExportError, "page limit"):
                    inventory.collect(self.meta, Path(work), "both", 1)
                summary = inventory.collect(self.meta, Path(work), "both", 4)
            items = json.loads(Path(summary["json_path"]).read_text("utf-8"))["entries"]
            self.assertEqual(len(items), 2)
            self.assertEqual(self.cursors, ["", self.items[0]["path"]])

    def test_uncertain_native_page_ack_queries_original_receipt_without_replay(self):
        complete = {"status": "completed", "generation": 7,
                    "root": self.root, "items": [], "has_more": False}
        with patch.object(inventory, "request",
                          side_effect=RuntimeError("Lost native WSS acknowledgement")) as invoke, \
             patch.object(inventory, "status_for",
                          return_value=("completed", complete)) as status:
            state, body, receipt_id = inventory.call(
                "rounder.inventory.page",
                {"generation": 7, "after": "/Apps/Koikatsu/a", "format": "json"})
        self.assertEqual(state, "completed")
        self.assertIs(body, complete)
        self.assertTrue(receipt_id.startswith("rounder-export-"))
        invoke.assert_called_once()
        status.assert_called_once_with(receipt_id)

    def test_transient_phone_dns_failure_recovers_without_restart(self):
        temporarily_failed = dict(self.meta,
            status="failed", reason="index_error", index_building=True,
            index_error='Unable to resolve host "www.terabox.com": No address associated with hostname',
            complete_for_index_generation=False)
        resumed = dict(self.meta, status="accepted", index_building=True,
                       complete_for_index_generation=False)
        with patch.object(inventory, "call", return_value=(
                "failed", temporarily_failed, "rounder-dns-retry-123")) as invoke, \
             patch.object(inventory, "status_for", side_effect=[
                ("accepted", resumed), ("completed", self.meta)]) as status, \
             patch.object(inventory.time, "sleep"):
            result = inventory.wait_for_inventory(20.0, 0.5)
        self.assertEqual(result["generation"], 7)
        invoke.assert_called_once()
        self.assertEqual(status.call_count, 2)

    def test_subtree_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as work:
            def malicious(*a, **kw):
                return Reply(envelope({
                    "status": "completed", "root": self.root,
                    "generation": 7, "account_fingerprint": "d54c50b6ad0e2edcb1f2ade3", "items": [
                        {**self.items[0], "path": "/Private/other.txt"}],
                    "count": 1, "next_after": "/Private/other.txt",
                    "has_more": False,
                }))
            with patch.object(inventory, "request", side_effect=malicious):
                with self.assertRaises(inventory.ExportError):
                    inventory.collect(self.meta, Path(work), "json", 2)


if __name__ == "__main__":
    unittest.main()
