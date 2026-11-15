import unittest

from workforce_intelligence.records import deduplicate_findings, normalize_finding
from workforce_intelligence.research_modes import (
    MANUFACTURING_INDUSTRIES, OTHER_INDUSTRIES, build_research_plan,
)


class ResearchModeTests(unittest.TestCase):
    def test_default_is_manufacturing(self):
        plan = build_research_plan("manufacturing")
        self.assertEqual(plan.industries, MANUFACTURING_INDUSTRIES)

    def test_other_industries_excludes_manufacturing(self):
        plan = build_research_plan("explore other industries")
        self.assertEqual(plan.industries, OTHER_INDUSTRIES)

    def test_all_industries_contains_both(self):
        plan = build_research_plan("all")
        self.assertTrue(set(MANUFACTURING_INDUSTRIES).issubset(plan.industries))
        self.assertTrue(set(OTHER_INDUSTRIES).issubset(plan.industries))

    def test_invalid_mode_rejected(self):
        with self.assertRaises(ValueError):
            build_research_plan("india only")


class RecordTests(unittest.TestCase):
    def test_geography_is_not_inferred(self):
        row = normalize_finding({"country_searched": "Germany", "problem_type": "Skill shortage"})
        self.assertIsNone(row["country"])

    def test_duplicate_rows_removed(self):
        row = {"problem_type": "Skill shortage", "country": "Germany",
               "source_url": "https://example.org/report", "description": "Shortage"}
        self.assertEqual(len(deduplicate_findings([row, row])), 1)

    def test_invalid_url_rejected(self):
        with self.assertRaises(ValueError):
            normalize_finding({"source_url": "javascript:alert(1)"})


if __name__ == "__main__":
    unittest.main()
