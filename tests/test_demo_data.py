import ast
import json
import tempfile
import unittest
from pathlib import Path

from frontend.demo_data import load_demo_findings


class OfflineDemoTests(unittest.TestCase):
    def test_loader_normalizes_fields_and_week_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.jsonl"
            path.write_text(json.dumps({
                "industry": "Manufacturing",
                "problem_type": "Skills shortage",
                "description": "Shortage of skilled workers",
                "country": "Germany",
                "source_url": "https://example.org/article",
                "weeks_seen": ["2026-11-16", "2026-11-09"],
            }) + "\n", encoding="utf-8")
            result = load_demo_findings(path)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["Industry"], "Manufacturing")
        self.assertEqual(result[0]["Identified Problem"], "Skills shortage")
        self.assertEqual(result[0]["Country"], "Germany")
        self.assertEqual(result[0]["Source URL"], "https://example.org/article")
        self.assertEqual(result[0]["Weeks Seen"], 2)
        self.assertIsInstance(result[0]["Weeks Seen"], int)
        self.assertEqual(result[0]["Observation Weeks"], "2026-11-09, 2026-11-16")

    def test_accepts_string_weeks_and_skips_bad_json_non_object_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.jsonl"
            valid = json.dumps({"industry": "Construction", "weeks_seen": "2026-11-16, 2026-11-09"})
            path.write_text("\nnot-json\n[]\n" + valid + "\n", encoding="utf-8")
            result = load_demo_findings(path)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["Industry"], "Construction")
        self.assertEqual(result[0]["Weeks Seen"], 2)
        self.assertIsInstance(result[0]["Weeks Seen"], int)
        self.assertEqual(result[0]["Observation Weeks"], "2026-11-09, 2026-11-16")

    def test_missing_file_returns_empty(self):
        result = load_demo_findings(Path("/nonexistent/demo-history.jsonl"))
        self.assertEqual(result, [])

    def test_demo_entrypoint_is_syntactically_valid(self):
        app_path = Path(__file__).resolve().parents[1] / "frontend" / "demo.py"
        ast.parse(app_path.read_text(encoding="utf-8"), filename=str(app_path))


if __name__ == "__main__":
    unittest.main()
