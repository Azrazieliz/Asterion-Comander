"""Regression: never reappend an entire interaction-session module."""
import ast
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "asterion_remote" / "interaction_sessions.py"

class SessionSourceIntegrityTests(unittest.TestCase):
    def test_session_module_has_single_definitions(self):
        tree = ast.parse(SOURCE.read_text("utf8"), filename=str(SOURCE))
        names = Counter(item.name for item in tree.body
                        if isinstance(item, (ast.FunctionDef, ast.ClassDef)))
        for name in ("Step", "SessionRequest", "start", "worker",
                     "status", "cancel", "update", "perform"):
            self.assertEqual(names[name], 1, name)
        self.assertEqual(sum(names.values()), len(names))

    def test_source_compiles_without_loading_any_device(self):
        source = SOURCE.read_text("utf8")
        compile(source, str(SOURCE), "exec")
        self.assertIn("session_journal.reserve_if_new", source)
        self.assertIn("replay_allowed", source)
        self.assertIn("assert_package", source)

if __name__ == "__main__":
    unittest.main()
