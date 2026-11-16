"""Public Control dashboard exposes only read-only evidence-backed diagnostics."""
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / "asterion_remote" / "static"


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.tabs = {}
        self.sections = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            assert a["id"] not in self.ids, "Duplicate HTML ID " + a["id"]
            self.ids.add(a["id"])
            if tag == "section":
                self.sections[a["id"]] = a
        if tag == "button" and a.get("data-page"):
            self.tabs[a["data-page"]] = a


class DiagnosticDashboardTests(unittest.TestCase):
    def test_new_page_uses_existing_dashboard_and_is_publicly_navigable(self):
        parser = Elements()
        parser.feed((ROOT / "index.html").read_text(encoding="utf-8"))
        self.assertIn("diagnostics", parser.sections)
        self.assertIn("diagnostics", parser.tabs)
        self.assertNotIn("hidden", parser.tabs["diagnostics"])
        self.assertNotIn("internal", parser.sections["diagnostics"].get("class", ""))
        for element in (
            "diagnostic-refresh", "diagnostic-app", "diagnostic-window",
            "diagnostic-state", "diagnostic-metrics", "diagnostic-findings",
            "diagnostic-operations", "diagnostic-limits", "diagnostic-phone", "diagnostic-coverage", "diagnostic-guidance", "diagnostic-timeline",
        ):
            self.assertIn(element, parser.ids)

    def test_diagnostics_is_readonly_and_never_pretends_to_monitor_uninstrumented_apps(self):
        js = (ROOT / "app.js").read_text(encoding="utf-8")
        self.assertIn("async function loadDiagnostics()", js)
        self.assertIn("'/diagnostics/triage'+qp(query)", js)
        self.assertIn("Only diagnostic events that an app has actually reported", js)
        self.assertIn("async function loadPhoneDiagnosticEvidence()", js)
        self.assertIn("async function loadIntegrationCoverage()", js)
        self.assertIn("function readableDiagnosticIssue(", js)
        self.assertIn("function diagnosticAppAction(", js)
        self.assertIn("No diagnostic events recorded in the selected period.", js)
        self.assertIn("HTTP 403 alone does not show a geographical block.", js)
        self.assertIn("\'/diagnostics/coverage\'", js)
        self.assertIn("'/phone/diagnostics/events'+qp({since:0,limit:1})", js)
        self.assertIn("'asterion_control_process_only'", js)
        self.assertIn("Only Control’s own process is visible", js)
        self.assertIn("A historical queued entry does not prove", js)
        self.assertIn("document.createElement", js)
        self.assertIn("body.textContent=detail", js)
        self.assertNotIn("innerHTML", js)
        segment = js.split("async function loadDiagnostics()", 1)[1].split(
            "async function discoverMonitors()", 1)[0]
        self.assertNotIn("method:'POST'", segment)
        self.assertNotIn("method:'DELETE'", segment)
        self.assertNotIn("eval(", segment)

    def test_mobile_layout_is_renderable(self):
        css = (ROOT / "style.css").read_text(encoding="utf-8")
        self.assertIn(".diagnostic-grid", css)
        self.assertIn(".diagnostic-records", css)
        self.assertIn("@media(max-width:700px)", css)
        self.assertEqual(css.count("{"), css.count("}"))


if __name__ == "__main__":
    unittest.main()
