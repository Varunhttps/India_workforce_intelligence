import unittest
from datetime import date

from workforce_intelligence.source_quality import (
    canonicalize_url, deduplicate_sources, assess_relevance, recency_assessment,
    assess_geography, source_quality_assessment, evaluate_candidate, evaluate_candidates,
)


class SourceQualityTests(unittest.TestCase):
    def test_url_normalization_removes_tracking_and_fragment(self):
        self.assertEqual(
            canonicalize_url("HTTPS://WWW.Example.com/path/?utm_source=x&b=2#frag"),
            "https://example.com/path?b=2",
        )

    def test_duplicate_urls_merge_and_keep_aliases(self):
        rows = deduplicate_sources([
            {"url": "https://www.example.com/article?utm_source=a", "title": "Article"},
            {"source_url": "https://example.com/article", "snippet": "Snippet"},
        ])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["duplicate_count"], 2)
        self.assertEqual(rows[0]["snippet"], "Snippet")
        self.assertEqual(len(rows[0]["original_urls"]), 2)

    def test_text_fallback_duplicates_when_urls_missing(self):
        rows = deduplicate_sources([
            {"title": "Worker shortage report", "snippet": "Factories need skilled workers"},
            {"title": "Worker shortage report", "snippet": "Factories need skilled workers"},
        ])
        self.assertEqual(len(rows), 1)

    def test_manufacturing_relevance_is_flagged(self):
        result = assess_relevance(title="Factory production worker shortage",
                                 industry="Automotive manufacturing")
        self.assertGreaterEqual(result["manufacturing_relevance_score"], 3)
        self.assertTrue(result["manufacturing_focus_priority"])
        self.assertEqual(result["workforce_relevance_label"], "Strong workforce relevance")

    def test_non_manufacturing_candidate_not_misclassified(self):
        result = assess_relevance(title="Healthcare nurses recruitment", industry="Healthcare")
        self.assertFalse(result["manufacturing_focus_priority"])
        self.assertEqual(result["manufacturing_relevance_label"], "Not manufacturing-specific")

    def test_recency_bands_and_unknown(self):
        recent = recency_assessment("2026-11-10", date(2026, 11, 21))
        old = recency_assessment("2023-01-01", date(2026, 11, 21))
        unknown = recency_assessment(None, date(2026, 11, 21))
        self.assertEqual(recent["recency_label"], "Recent (0–30 days)")
        self.assertEqual(old["recency_score"], 0)
        self.assertIsNone(unknown["age_days"])
        self.assertEqual(unknown["recency_label"], "Date unknown")

    def test_geography_distinguishes_search_target(self):
        result = assess_geography(country_searched="Germany", title="Global workforce trends")
        self.assertEqual(result["geography_label"], "Search geography only")
        explicit = assess_geography(actual_geography="Germany", country_searched="India")
        self.assertEqual(explicit["geography_label"], "Explicit geography supplied")

    def test_domain_quality_is_heuristic(self):
        result = source_quality_assessment("https://www.bls.gov/report", source_class="Government")
        self.assertEqual(result["source_quality_score"], 4)
        self.assertIn("not an endorsement", result["source_quality_note"])

    def test_evaluate_candidate_is_non_destructive_and_annotates(self):
        result = evaluate_candidate({"url": "https://example.com", "title": "Manufacturing workforce skills shortage",
                                   "industry": "Manufacturing", "country_searched": "India"},
                                  reference_date=date(2026, 11, 21))
        self.assertIn("source_quality_score", result)
        self.assertIn("workforce_relevance_score", result)
        self.assertIn("recency_label", result)
        self.assertEqual(result["geography_label"], "Search geography only")

    def test_batch_evaluation_deduplicates_first(self):
        results = evaluate_candidates([
            {"url": "https://example.com/a?utm_campaign=x", "title": "Manufacturing worker shortage"},
            {"url": "https://example.com/a", "title": "Duplicate"},
        ], reference_date=date(2026, 11, 21))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["duplicate_count"], 2)


if __name__ == "__main__":
    unittest.main()
