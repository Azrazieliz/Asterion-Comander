"""Private GitHub relay can request only bounded diagnostic summaries."""
import unittest
from unittest.mock import patch

from asterion_remote import github_bridge


class BridgeDiagnosticTriageTests(unittest.TestCase):
    def test_readonly_diagnostic_query_is_encoded_and_authenticated(self):
        request = {
            "op": "pc_diagnostic_triage",
            "params": {
                "app": "asterion.downloader",
                "lookback_minutes": 30,
                "limit": 200,
                "stale_after_seconds": 600,
            },
        }
        with patch.object(github_bridge, "pc", return_value={"ok": True}) as api:
            self.assertEqual(github_bridge.run(request, "paired-bearer"), {"ok": True})
        args = api.call_args.args
        self.assertEqual(args[1], "paired-bearer")
        self.assertTrue(args[0].startswith("/api/v1/diagnostics/triage?"))
        self.assertIn("app=asterion.downloader", args[0])
        self.assertIn("limit=200", args[0])

    def test_disallows_unbounded_or_arbitrary_api_proxying(self):
        invalid = [
            {"app": "../admin"},
            {"app": "asterion.download/../../tokens"},
            {"limit": 3001},
            {"limit": True},
            {"lookback_minutes": -1},
            {"stale_after_seconds": 29},
            {"path": "/api/v1/secret"},
            {"endpoint": "https://example.invalid"},
        ]
        for params in invalid:
            with self.subTest(params=params):
                with patch.object(github_bridge, "pc") as api:
                    with self.assertRaises(ValueError):
                        github_bridge.run(
                            {"op": "pc_diagnostic_triage", "params": params},
                            "paired-bearer")
                    api.assert_not_called()

    def test_bounded_native_android_journal(self):
        with patch.object(github_bridge, "pc", return_value={
            "ok": True, "scope": "asterion_control_process_only",
            "events": []}) as api:
            result=github_bridge.run(
                {"op": "phone_diagnostic_events",
                 "params": {"since": 37, "limit": 40}}, "paired-bearer")
        self.assertEqual(result["scope"], "asterion_control_process_only")
        self.assertEqual(api.call_args.args[0],
                         "/api/v1/phone/diagnostics/events?since=37&limit=40")
        self.assertEqual(api.call_args.args[1], "paired-bearer")

    def test_native_journal_rejects_privileged_or_unbounded_requests(self):
        rejected=[
            {"since": -1}, {"since": 2**62}, {"since": True},
            {"limit": 0}, {"limit": 81}, {"limit": "40"},
            {"path": "/other/app"}, {"app": "com.other.app"}
        ]
        for params in rejected:
            with self.subTest(params=params):
                with patch.object(github_bridge,"pc") as api:
                    with self.assertRaises(ValueError):
                        github_bridge.run(
                            {"op": "phone_diagnostic_events", "params": params},
                            "paired-bearer")
                    api.assert_not_called()

    def test_bounded_cross_device_snapshot(self):
        with patch.object(github_bridge,"pc",return_value={"ok":True}) as api:
            self.assertTrue(github_bridge.run(
                {"op":"pc_diagnostic_snapshot","params":{
                    "app":"asterion.control","limit":120,"phone":True}},
                "paired-bearer")["ok"])
        self.assertIn("app=asterion.control",api.call_args.args[0])
        self.assertIn("phone=True",api.call_args.args[0])
        self.assertEqual(api.call_args.args[1],"paired-bearer")
        for params in [{"phone":"true"},{"limit":9999},
                       {"app":"../secrets"},{"arbitrary_path":"/admin"}]:
            with self.subTest(params=params):
                with patch.object(github_bridge,"pc") as forbidden:
                    with self.assertRaises(ValueError):
                        github_bridge.run(
                            {"op":"pc_diagnostic_snapshot","params":params},
                            "paired-bearer")
                    forbidden.assert_not_called()

    def test_ordinary_get_still_rejects_query_body(self):
        with patch.object(github_bridge, "pc") as api:
            with self.assertRaises(ValueError):
                github_bridge.run(
                    {"op": "pc_status", "params": {"limit": 100}},
                    "paired-bearer")
            api.assert_not_called()


if __name__ == "__main__":
    unittest.main()
