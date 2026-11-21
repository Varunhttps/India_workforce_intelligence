import unittest
from workforce_intelligence.trend_analysis import analyze_weekly_trends, monday_week


class WeeklyTrendAnalysisTests(unittest.TestCase):
    def test_new_problem_this_week(self):
        records = [{
            "industry": "Manufacturing", "problem_type": "Technician shortage",
            "country": "Germany", "source_url": "https://example.org/a",
            "first_seen": "2026-11-17", "last_seen": "2026-11-17",
            "first_seen_week": "2026-11-16", "last_seen_week": "2026-11-16",
            "weeks_seen": ["2026-11-16"],
        }]
        result = analyze_weekly_trends(records, current_week="2026-11-16")
        self.assertEqual(result[0]["signal_status"], "New this week")
        self.assertEqual(result[0]["weeks_observed"], 1)

    def test_problem_active_after_prior_week(self):
        records = [{
            "industry": "Manufacturing", "problem_type": "Technician shortage",
            "country": "Germany", "source_url": "https://example.org/a",
            "first_seen": "2026-11-10", "last_seen": "2026-11-17",
            "first_seen_week": "2026-11-09", "last_seen_week": "2026-11-16",
            "weeks_seen": ["2026-11-09", "2026-11-16"],
        }]
        result = analyze_weekly_trends(records, current_week="2026-11-16")
        self.assertEqual(result[0]["signal_status"], "Active this week")
        self.assertEqual(result[0]["weeks_observed"], 2)

    def test_missing_latest_week_is_not_marked_resolved(self):
        records = [{
            "industry": "Manufacturing", "problem_type": "Technician shortage",
            "country": "Germany", "source_url": "https://example.org/a",
            "first_seen": "2026-11-10", "last_seen": "2026-11-10",
            "first_seen_week": "2026-11-09", "last_seen_week": "2026-11-09",
            "weeks_seen": ["2026-11-09"],
        }]
        result = analyze_weekly_trends(records, current_week="2026-11-16")
        self.assertEqual(result[0]["signal_status"], "Not observed this week")

    def test_aggregate_problem_across_countries_and_sources(self):
        base = {
            "industry": "Manufacturing", "problem_type": "Skills gap",
            "first_seen": "2026-11-10", "last_seen": "2026-11-17",
            "first_seen_week": "2026-11-09", "last_seen_week": "2026-11-16",
            "weeks_seen": ["2026-11-09", "2026-11-16"],
        }
        records = [
            {**base, "country": "Germany", "source_url": "https://example.org/a"},
            {**base, "country": "France", "source_url": "https://example.org/b"},
        ]
        result = analyze_weekly_trends(records, current_week="2026-11-16")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["country_count"], 2)
        self.assertEqual(result[0]["source_count"], 2)
        self.assertEqual(result[0]["weeks_observed"], 2)

    def test_week_start_monday(self):
        self.assertEqual(monday_week("2026-11-19"), "2026-11-16")


if __name__ == "__main__":
    unittest.main()
