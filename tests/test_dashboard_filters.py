import unittest
import pandas as pd

from workforce_intelligence.dashboard_filters import industry_options, filter_frames_by_industry, weekly_statuses, ALL_INDUSTRIES


class DashboardIndustryFilterTests(unittest.TestCase):
    def setUp(self):
        self.frames = {
            "Market Research": pd.DataFrame([
                {"Industry": "Manufacturing", "Problem": "A"},
                {"Industry": "Healthcare", "Problem": "B"},
                {"Industry": " manufacturing ", "Problem": "C"},
                {"Industry": None, "Problem": "D"},
            ]),
            "Source Register": pd.DataFrame([{"Source": "no industry column"}]),
            "Weekly Trends": pd.DataFrame([
                {"Industry": "Healthcare", "Signal": "New"},
                {"Industry": "Manufacturing", "Signal": "Stable"},
            ]),
            "Empty": pd.DataFrame(),
        }

    def test_options_are_unique_sorted_and_include_all(self):
        self.assertEqual(industry_options(self.frames), [ALL_INDUSTRIES, "Healthcare", "Manufacturing"])

    def test_filter_applies_case_insensitive_exact_match_and_trims(self):
        filtered = filter_frames_by_industry(self.frames, "manufacturing")
        self.assertEqual(len(filtered["Market Research"]), 2)
        self.assertEqual(len(filtered["Weekly Trends"]), 1)
        self.assertEqual(len(filtered["Source Register"]), 1)
        self.assertTrue(filtered["Empty"].empty)
        self.assertEqual(filtered["Market Research"].iloc[0]["Problem"], "A")

    def test_all_industries_returns_copies_without_mutating_input(self):
        filtered = filter_frames_by_industry(self.frames)
        self.assertEqual(len(filtered["Market Research"]), 4)
        self.assertIsNot(filtered["Market Research"], self.frames["Market Research"])
        self.assertEqual(len(self.frames["Market Research"]), 4)

    def test_missing_industry_column_is_preserved(self):
        filtered = filter_frames_by_industry(self.frames, "Healthcare")
        self.assertEqual(filtered["Source Register"].iloc[0]["Source"], "no industry column")


    def test_weekly_statuses_derive_from_first_and_last_seen_without_status_column(self):
        frame = pd.DataFrame([
            {"First Seen": "2026-11-17", "Last Seen": "2026-11-17"},
            {"First Seen": "2026-11-02", "Last Seen": "2026-11-20"},
            {"First Seen": "2026-10-05", "Last Seen": "2026-10-19"},
            {"First Seen": "", "Last Seen": ""},
        ])
        statuses = weekly_statuses(frame, current_week="2026-11-16")
        self.assertEqual(statuses.tolist(), [
            "New this week", "Recurring this week", "Last seen before this week", "Unknown"
        ])

    def test_observation_weeks_are_used_and_stale_legacy_labels_ignored(self):
        frame = pd.DataFrame([
            {"First Seen": "2026-11-02", "Latest Week": "2026-11-16",
             "Observation Weeks": "2026-11-02, 2026-11-16, 2026-11-23", "Weekly Status": "Old label"},
            {"First Seen": "2026-11-23", "Latest Week": "2026-11-23",
             "Observation Weeks": "2026-11-23"},
            {"First Seen": "2026-11-02", "Latest Week": "2026-11-09",
             "Observation Weeks": "2026-11-02, 2026-11-09"},
            {"First Seen": "02112026", "Latest Week": "09112026",
             "Observation Weeks": "02112026, 23112026"},
        ])
        statuses = weekly_statuses(frame, current_week="2026-11-23")
        self.assertEqual(statuses.tolist(), [
            "Recurring this week", "New this week", "Last seen before this week", "Recurring this week"
        ])

if __name__ == "__main__":
    unittest.main()
