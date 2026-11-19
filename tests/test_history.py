import tempfile
import unittest
from pathlib import Path
from workforce_intelligence.history import update_history, week_start

class HistoryTests(unittest.TestCase):
    def test_new_then_recurring_finding(self):
        finding = {"problem_type":"Skills shortage","description":"Plants report unfilled roles",
                   "country":"Germany","industry":"Manufacturing","source_url":"https://example.org/a"}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.jsonl"
            first = update_history([finding], path, observed_at="2026-11-15")
            self.assertEqual(len(first["new"]), 1)
            self.assertEqual(len(first["recurring"]), 0)
            second = update_history([finding], path, observed_at="2026-11-22")
            self.assertEqual(len(second["new"]), 0)
            self.assertEqual(len(second["recurring"]), 1)
            self.assertEqual(second["recurring"][0]["first_seen"], "2026-11-15")
            self.assertEqual(second["recurring"][0]["occurrences"], 2)
            self.assertEqual(second["history_records"], 1)
            self.assertEqual(first["week_start"], "2026-11-09")
            self.assertEqual(second["recurring"][0]["weekly_status"], "Recurring this week")
            self.assertEqual(second["recurring"][0]["weeks_seen"], ["2026-11-09", "2026-11-16"])

    def test_week_start_is_monday(self):
        self.assertEqual(week_start("2026-11-19"), "2026-11-16")

    def test_different_source_is_separate_observation(self):
        a={"problem_type":"Skills shortage","description":"Plants report unfilled roles","industry":"Manufacturing","source_url":"https://example.org/a"}
        b={**a,"source_url":"https://example.org/b"}
        with tempfile.TemporaryDirectory() as tmp:
            result=update_history([a,b],Path(tmp)/"history.jsonl",observed_at="2026-11-15")
            self.assertEqual(len(result["new"]),2)

if __name__=="__main__":
    unittest.main()
