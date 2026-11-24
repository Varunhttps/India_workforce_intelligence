import json
import tempfile
import unittest
from pathlib import Path

from workforce_intelligence.source_history import update_source_history, save_source_history
from workforce_intelligence.google_sheets import build_sheet_payloads


class SourceHistoryTests(unittest.TestCase):
    def test_first_found_date_is_preserved_and_new_source_gets_run_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sources.jsonl"
            first = [{"Source title": "Old source", "Source URL": "https://example.com/old",
                      "Source platform": "Web", "Industry searched": "Manufacturing"}]
            records = update_source_history(first, path, observed_at="2026-11-23")
            second = first + [{"Source title": "New source", "Source URL": "https://example.com/new",
                              "Source platform": "Web", "Industry searched": "Logistics"}]
            records = update_source_history(second, path, observed_at="2026-11-24")
            by_url = {row["source_url"]: row for row in records}
            self.assertEqual(by_url["https://example.com/old"]["first_found_date"], "2026-11-23")
            self.assertEqual(by_url["https://example.com/new"]["first_found_date"], "2026-11-24")

    def test_migrated_sheet_dates_are_saved_permanently(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sources.jsonl"
            migrated = [
                {"source_url": "https://example.com/old", "source_title": "Legacy source",
                 "first_found_date": "2026-11-20"},
                {"source_url": "https://example.com/blank", "source_title": "Undated source",
                 "first_found_date": ""},
            ]
            save_source_history(migrated, path)
            loaded = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            by_url = {row["source_url"]: row for row in loaded}
            self.assertEqual(by_url["https://example.com/old"]["first_found_date"], "2026-11-20")
            self.assertEqual(by_url["https://example.com/blank"]["first_found_date"], "")

    def test_source_register_uses_historical_access_dates(self):
        sources = [{"Source title": "Current source", "Source URL": "https://example.com/one",
                    "Source platform": "Web", "Industry searched": "Manufacturing"}]
        history = [{"source_url": "https://example.com/one", "source_title": "Current source",
                    "source_platform": "Web", "industry": "Manufacturing", "first_found_date": "2026-11-20"}]
        payload = build_sheet_payloads([], sources, research_date="2026-11-24", source_history_records=history)
        headers, row = payload["Source Register"][0], payload["Source Register"][1]
        self.assertEqual(dict(zip(headers, row))["Access Date"], "2026-11-20")


if __name__ == "__main__":
    unittest.main()
