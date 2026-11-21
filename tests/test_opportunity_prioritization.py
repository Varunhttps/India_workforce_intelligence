import unittest
from datetime import date
import pandas as pd

from workforce_intelligence.opportunity_prioritization import (
    build_opportunity_priorities, classify_track, score_opportunity,
)


class OpportunityPriorityTests(unittest.TestCase):
    def test_track_classification(self):
        self.assertEqual(classify_track("Hiring demand", "Talent acquisition"), "Staffing & Recruitment")
        self.assertEqual(classify_track("Skills planning", "Capacity forecasting"), "Nexplan — Enterprise Planning")

    def test_scoring_is_bounded_and_componentized(self):
        result = score_opportunity(10, "2026-11-20", "Major operational disruption", ["High — official publisher"], "Planning", today=date(2026, 11, 21))
        self.assertEqual(result["score"], 93)
        self.assertEqual(result["priority"], "High priority")
        self.assertEqual(sum(result["components"].values()), result["score"])

    def test_unknown_evidence_does_not_get_inflated_score(self):
        result = score_opportunity(0, "", "", [], "", today=date(2026, 11, 21))
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["priority"], "Monitor")

    def test_build_groups_maps_and_links_sources(self):
        research = pd.DataFrame([
            {"Research ID": "R1", "Industry": "Manufacturing", "Identified Problem": "Hiring gap",
             "Business Impact": "Production delay", "Country": "India", "Research Date": "2026-11-20",
             "Source URL": "https://a.example"},
            {"Research ID": "R2", "Industry": "Manufacturing", "Identified Problem": "Hiring gap",
             "Business Impact": "Operational cost", "Country": "Germany", "Research Date": "2026-11-19",
             "Source URL": "https://b.example"},
        ])
        mapped = pd.DataFrame([{
            "Industry": "Manufacturing", "Market Need": "Hiring demand",
            "Proposed Product Capability": "Talent acquisition and demand planning",
            "Suggested Feature & Description": "Forecast vacancy demand",
            "Expected Business Value": "Improve hiring visibility",
            "Related Research IDs": "R1, R2", "Supporting Source URLs": "",
        }])
        register = pd.DataFrame([
            {"Source URL": "https://a.example", "Source Credibility Assessment": "High — official"},
            {"Source URL": "https://b.example", "Source Credibility Assessment": "Moderate — trade body"},
        ])
        result = build_opportunity_priorities(research, mapped, register, today=date(2026, 11, 21))
        self.assertEqual(len(result), 1)
        row = result[0]
        self.assertEqual(row["Track"], "Staffing & Recruitment")
        self.assertEqual(row["Source Count"], 2)
        self.assertEqual(row["Country Count"], 2)
        self.assertEqual(row["Supporting Research IDs"], "R1, R2")
        self.assertIn("High priority", row["Priority"])
        self.assertEqual(row["Score"], sum(row["Score Breakdown"].values()))


if __name__ == "__main__":
    unittest.main()
