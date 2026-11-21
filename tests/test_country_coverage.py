import unittest

from workforce_intelligence.country_coverage import (
    normalize_country, country_region, summarize_country_coverage, build_country_industry_matrix,
)


class CountryCoverageTests(unittest.TestCase):
    def setUp(self):
        self.findings = [
            {"Country": "USA", "Industry": "Automotive manufacturing", "Identified Problem": "Worker shortage", "Source URL": "https://a.test", "Research Date": "2026-11-20"},
            {"Country": "United States", "Industry": "Healthcare", "Identified Problem": "Nurse recruitment", "Source URL": "https://b.test", "Research Date": "2026-10-01"},
            {"country": "Germany", "industry": "Manufacturing", "problem_type": "Skills shortage", "source_url": "https://c.test", "publication_date": "2026-11"},
            {"Country": "Unknown", "Industry": "Retail", "Identified Problem": "Hiring", "Source URL": "https://d.test"},
            {"Country": "Global", "Industry": "IT", "Identified Problem": "Talent", "Source URL": "https://e.test"},
        ]

    def test_country_aliases_normalize(self):
        self.assertEqual(normalize_country("USA"), "United States")
        self.assertEqual(normalize_country("  uk  "), "United Kingdom")
        self.assertEqual(normalize_country("Unknown"), "")

    def test_region_mapping_and_fallback(self):
        self.assertEqual(country_region("Germany"), "Europe")
        self.assertEqual(country_region("United States"), "North America")
        self.assertEqual(country_region("Atlantis"), "Other / unclassified")

    def test_summary_counts_only_explicit_geography_and_deduplicates_sources(self):
        rows = summarize_country_coverage(self.findings)
        usa = next(row for row in rows if row["Country"] == "United States")
        self.assertEqual(usa["Findings"], 2)
        self.assertEqual(usa["Distinct sources"], 2)
        self.assertEqual(usa["Distinct industries"], 2)
        self.assertEqual(usa["Manufacturing findings"], 1)
        self.assertEqual(usa["Region"], "North America")
        self.assertEqual(len(rows), 2)

    def test_target_countries_include_zero_coverage(self):
        rows = summarize_country_coverage(self.findings, target_countries=["Japan", "USA"])
        japan = next(row for row in rows if row["Country"] == "Japan")
        self.assertEqual(japan["Findings"], 0)
        self.assertEqual(japan["Distinct sources"], 0)

    def test_industry_matrix_aggregates_by_country(self):
        matrix = build_country_industry_matrix(self.findings, target_countries=["Japan"])
        self.assertEqual(matrix["United States"]["Healthcare"], 1)
        self.assertEqual(matrix["United States"]["Automotive manufacturing"], 1)
        self.assertIn("Japan", matrix)
        self.assertEqual(matrix["Japan"], {})


if __name__ == "__main__":
    unittest.main()
