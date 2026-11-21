import unittest
import pandas as pd

from workforce_intelligence.dashboard_filters import industry_options, filter_frames_by_industry, ALL_INDUSTRIES


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


if __name__ == "__main__":
    unittest.main()
