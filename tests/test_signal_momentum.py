import unittest
from workforce_intelligence.signal_momentum import analyze_signal_momentum, rank_emerging_industries


class SignalMomentumTests(unittest.TestCase):
    def test_weekly_source_counts_and_direction(self):
        records = [
            {"industry": "Manufacturing", "problem_type": "Talent shortage", "source_url": "a", "weeks_seen": ["2026-11-09", "2026-11-16"]},
            {"industry": "Manufacturing", "problem_type": "Talent shortage", "source_url": "b", "weeks_seen": ["2026-11-16"]},
            {"industry": "Manufacturing", "problem_type": "Talent shortage", "source_url": "c", "weeks_seen": ["2026-11-09"]},
        ]
        row = analyze_signal_momentum(records, "2026-11-16")[0]
        self.assertEqual(row["previous_source_count"], 2)
        self.assertEqual(row["current_source_count"], 2)
        self.assertEqual(row["trend"], "Stable evidence")

    def test_increasing_and_decreasing_evidence(self):
        records = [
            {"industry": "A", "problem_type": "Hiring shortage", "source_url": "1", "weeks_seen": ["2026-11-09", "2026-11-16"]},
            {"industry": "A", "problem_type": "Hiring shortage", "source_url": "2", "weeks_seen": ["2026-11-16"]},
            {"industry": "B", "problem_type": "Skills gap", "source_url": "3", "weeks_seen": ["2026-11-09"]},
        ]
        rows = analyze_signal_momentum(records, "2026-11-16")
        a = next(r for r in rows if r["industry"] == "A")
        b = next(r for r in rows if r["industry"] == "B")
        self.assertEqual(a["trend"], "Increasing evidence")
        self.assertEqual(b["trend"], "Not observed this week")

    def test_missing_week_does_not_mean_problem_resolved(self):
        row = analyze_signal_momentum([{"industry": "M", "problem_type": "Capacity gap", "source_url": "x", "weeks_seen": ["2026-11-09"]}], "2026-11-16")[0]
        self.assertEqual(row["trend"], "Not observed this week")
        self.assertIn("do not prove", row["interpretation_note"])

    def test_opportunity_tags(self):
        row = analyze_signal_momentum([{"industry": "M", "problem_type": "Hiring shortage", "source_url": "x", "weeks_seen": ["2026-11-16"]}], "2026-11-16")[0]
        self.assertEqual(row["staffing_opportunity_signal"], "Candidate")
        self.assertEqual(row["nexplan_planning_signal"], "Review")

    def test_industry_ranking_prioritizes_source_count_then_diversity(self):
        rows = [
            {"industry": "A", "problem_type": "p1", "current_source_count": 2, "trend": "Increasing evidence", "staffing_opportunity_signal": "Candidate", "nexplan_planning_signal": "Review"},
            {"industry": "A", "problem_type": "p2", "current_source_count": 1, "trend": "Stable", "staffing_opportunity_signal": "Review", "nexplan_planning_signal": "Candidate"},
            {"industry": "B", "problem_type": "p3", "current_source_count": 3, "trend": "Stable", "staffing_opportunity_signal": "Review", "nexplan_planning_signal": "Review"},
        ]
        ranked = rank_emerging_industries(rows)
        self.assertEqual(ranked[0]["industry"], "A")
        self.assertEqual(ranked[0]["distinct_problem_count"], 2)
        self.assertEqual(ranked[1]["industry"], "B")

    def test_zero_current_sources_is_not_labeled_decreasing(self):
        records = [{"industry":"M", "problem_type":"Hiring shortage", "source_url":"x", "weeks_seen":["2026-11-09"]}]
        row = analyze_signal_momentum(records, "2026-11-16")[0]
        self.assertEqual(row["trend"], "Not observed this week")

    def test_industry_ranking_uses_unique_sources_when_urls_are_available(self):
        rows = [
            {"industry":"A", "problem_type":"p1", "current_source_count":2, "current_source_urls":["a","b"], "trend":"Increasing evidence", "staffing_opportunity_signal":"Candidate", "nexplan_planning_signal":"Review"},
            {"industry":"A", "problem_type":"p2", "current_source_count":2, "current_source_urls":["b","c"], "trend":"Stable evidence", "staffing_opportunity_signal":"Review", "nexplan_planning_signal":"Candidate"},
            {"industry":"B", "problem_type":"p3", "current_source_count":3, "current_source_urls":["d","e","f"], "trend":"Stable evidence", "staffing_opportunity_signal":"Review", "nexplan_planning_signal":"Review"},
        ]
        ranked = rank_emerging_industries(rows)
        a = next(row for row in ranked if row["industry"] == "A")
        self.assertEqual(a["current_sources"], 3)
        self.assertFalse(a["source_count_estimated"])


if __name__ == "__main__":
    unittest.main()
