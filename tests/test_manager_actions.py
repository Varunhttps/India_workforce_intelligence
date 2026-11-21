import unittest
from datetime import date

from workforce_intelligence.manager_actions import recommend_manager_actions


class ManagerActionTests(unittest.TestCase):
    def test_rank_recent_multi_source_manufacturing_issue_higher(self):
        rows = [
            {"Industry": "Manufacturing", "Identified Problem": "Skilled labor hiring shortage",
             "Business Impact": "Production delay and capacity loss", "Country": "Germany",
             "Research Date": "2026-11-20", "Source URL": "https://a.example",
             "Weekly Status": "New this week", "Weeks Seen": "2026-11-16"},
            {"Industry": "Manufacturing", "Identified Problem": "Skilled labor hiring shortage",
             "Business Impact": "Production delay", "Country": "Japan",
             "Research Date": "2026-11-19", "Source URL": "https://b.example",
             "Weekly Status": "New this week", "Weeks Seen": "2026-11-16"},
            {"Industry": "Retail", "Identified Problem": "Hiring challenge",
             "Business Impact": "Hiring cost", "Country": "Canada",
             "Research Date": "2026-05-01", "Source URL": "https://c.example"},
        ]
        result = recommend_manager_actions(rows, today=date(2026, 11, 21))
        self.assertGreater(result[0]["Rank Score"], result[-1]["Rank Score"])
        self.assertEqual(result[0]["Manager Action"], "Validate hiring demand and pipeline")
        self.assertIn("time-to-fill", result[0]["Recommended Next Step"])

    def test_skills_problem_recommends_assessment(self):
        result = recommend_manager_actions([{
            "Industry": "Manufacturing", "Identified Problem": "Skills gap in technicians",
            "Business Impact": "Training cost", "Source URL": "https://a.example",
            "Research Date": "2026-11-20",
        }], today=date(2026, 11, 21))
        self.assertEqual(result[0]["Manager Action"], "Run a skills-gap assessment")

    def test_weekly_momentum_adds_explainable_bonus(self):
        row = {"Industry": "Technology", "Identified Problem": "Automation system adoption",
                "Business Impact": "Productivity", "Source URL": "https://a.example",
                "Research Date": "2026-11-20"}
        without = recommend_manager_actions([row], today=date(2026, 11, 21))[0]
        with_signal = recommend_manager_actions([row], [{
            "Industry": "Technology", "Workforce Problem": "Automation system adoption",
            "Signal Momentum": "Potentially worsening — evidence expansion",
        }], today=date(2026, 11, 21))[0]
        self.assertEqual(with_signal["Rank Score"], min(100, without["Rank Score"] + 10))
        self.assertIn("Weekly momentum bonus", with_signal["Score Rationale"])

    def test_unknown_and_empty_inputs_safe(self):
        self.assertEqual(recommend_manager_actions([]), [])
        rows = [{"Industry": "", "Identified Problem": "", "Source URL": "",
                  "Country": "Unknown", "Research Date": "bad date"}]
        result = recommend_manager_actions(rows, today=date(2026, 11, 21))
        self.assertEqual(result[0]["Priority"], "Monitor")

    def test_evidence_urls_are_retained(self):
        rows = [{"Industry": "Energy", "Identified Problem": "Safety risk",
                 "Business Impact": "Critical risk", "Country": "United States",
                 "Research Date": "2026-11-20", "Source URL": "https://source.example"}]
        result = recommend_manager_actions(rows, today=date(2026, 11, 21))
        self.assertEqual(result[0]["Evidence URLs"], ["https://source.example"])
        self.assertIn("Critical risk", result[0]["Score Rationale"])


if __name__ == "__main__":
    unittest.main()
