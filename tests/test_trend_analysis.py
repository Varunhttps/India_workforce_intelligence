import unittest

from workforce_intelligence.trend_analysis import (
    analyze_opportunity_changes,
    analyze_weekly_trends,
    monday_week,
)


def _record(problem="Technician shortage", source="https://example.org/a",
            country="Germany", weeks=None, first="2026-11-09", last="2026-11-16"):
    return {
        "industry": "Manufacturing",
        "problem_type": problem,
        "description": problem,
        "source_url": source,
        "country": country,
        "first_seen": first,
        "last_seen": last,
        "first_seen_week": monday_week(first),
        "last_seen_week": monday_week(last),
        "weeks_seen": weeks or [monday_week(first), monday_week(last)],
    }


class WeeklyTrendAnalysisTests(unittest.TestCase):
    CURRENT = "2026-11-16"

    def test_monday_week_normalizes_date(self):
        self.assertEqual(monday_week("2026-11-19"), self.CURRENT)

    def test_new_problem_has_new_status_and_emerging_flag(self):
        rows = [
            _record(source="https://example.org/a", country="Germany",
                    weeks=["2026-11-16"], first="2026-11-17", last="2026-11-17"),
            _record(source="https://example.org/b", country="France",
                    weeks=["2026-11-16"], first="2026-11-17", last="2026-11-17"),
        ]
        result = analyze_weekly_trends(rows, current_week=self.CURRENT)[0]
        self.assertEqual(result["signal_status"], "New this week")
        self.assertEqual(result["signal_momentum"], "New evidence")
        self.assertTrue(result["emerging_signal"])
        self.assertFalse(result["worsening_signal"])
        self.assertEqual(result["current_week_source_count"], 2)
        self.assertEqual(result["current_week_country_count"], 2)

    def test_source_and_country_expansion_marks_potentially_worsening(self):
        rows = [
            _record(source="https://example.org/a", country="Germany",
                    weeks=["2026-11-09", "2026-11-16"]),
            _record(source="https://example.org/b", country="Germany",
                    weeks=["2026-11-16"]),
            _record(source="https://example.org/c", country="France",
                    weeks=["2026-11-16"]),
        ]
        result = analyze_weekly_trends(rows, current_week=self.CURRENT)[0]
        self.assertEqual(result["signal_status"], "Active this week")
        self.assertEqual(result["previous_week_source_count"], 1)
        self.assertEqual(result["current_week_source_count"], 3)
        self.assertEqual(result["source_count_delta"], 2)
        self.assertEqual(result["country_count_delta"], 1)
        self.assertTrue(result["worsening_signal"])
        self.assertIn("Potentially worsening", result["signal_momentum"])

    def test_stable_evidence_has_no_growth_flags(self):
        rows = [
            _record(source="https://example.org/a", country="Germany",
                    weeks=["2026-11-09", "2026-11-16"]),
        ]
        result = analyze_weekly_trends(rows, current_week=self.CURRENT)[0]
        self.assertEqual(result["signal_momentum"], "Stable evidence")
        self.assertFalse(result["emerging_signal"])
        self.assertFalse(result["worsening_signal"])

    def test_not_observed_is_not_resolved(self):
        rows = [
            _record(source="https://example.org/a", country="Germany",
                    weeks=["2026-11-09"], first="2026-11-10", last="2026-11-10"),
        ]
        result = analyze_weekly_trends(rows, current_week=self.CURRENT)[0]
        self.assertEqual(result["signal_status"], "Not observed this week")
        self.assertEqual(result["signal_momentum"], "Not observed this week")
        self.assertFalse(result["worsening_signal"])

    def test_problem_group_deduplicates_sources_and_case(self):
        rows = [
            _record(problem="Skills gap", source="https://example.org/a",
                    country="Germany", weeks=["2026-11-09", "2026-11-16"]),
            _record(problem="skills GAP", source="https://example.org/a",
                    country="Germany", weeks=["2026-11-09", "2026-11-16"]),
            _record(problem="Skills gap", source="https://example.org/b",
                    country="France", weeks=["2026-11-16"]),
        ]
        result = analyze_weekly_trends(rows, current_week=self.CURRENT)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["source_count"], 2)
        self.assertEqual(result[0]["country_count"], 2)


class OpportunityChangeTests(unittest.TestCase):
    CURRENT = "2026-11-16"

    @staticmethod
    def _classifier(record, supporting_source_count=1):
        if "skills" not in record.get("problem_type", "").casefold():
            return None
        return {
            "market_need": "Skills planning",
            "capability": "Capability gap analysis",
            "feature": "Skills inventory and gap forecast",
            "business_value": "Target reskilling investment",
            "priority": "High" if supporting_source_count >= 2 else "Low",
        }

    def test_opportunity_expansion_across_weeks(self):
        rows = [
            _record(problem="Skills gap", source="https://example.org/a",
                    country="Germany", weeks=["2026-11-09", "2026-11-16"]),
            _record(problem="Skills gap", source="https://example.org/b",
                    country="France", weeks=["2026-11-16"]),
        ]
        result = analyze_opportunity_changes(rows, current_week=self.CURRENT, classifier=self._classifier)
        self.assertEqual(len(result), 1)
        row = result[0]
        self.assertEqual(row["change_status"], "Expanded evidence")
        self.assertEqual(row["source_count_delta"], 1)
        self.assertTrue(row["expanded_evidence"])
        self.assertEqual(row["priority"], "High")

    def test_new_opportunity_is_flagged(self):
        rows = [
            _record(problem="Skills gap", source="https://example.org/a",
                    country="Germany", weeks=["2026-11-16"],
                    first="2026-11-17", last="2026-11-17"),
        ]
        result = analyze_opportunity_changes(rows, current_week=self.CURRENT, classifier=self._classifier)
        self.assertEqual(result[0]["change_status"], "New this week")
        self.assertTrue(result[0]["new_this_week"])

    def test_unmapped_problems_do_not_create_opportunity_rows(self):
        rows = [_record(problem="Other unrelated concern")]
        result = analyze_opportunity_changes(rows, current_week=self.CURRENT, classifier=self._classifier)
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
