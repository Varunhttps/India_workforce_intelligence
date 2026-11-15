import json
import unittest
from unittest.mock import patch

from workforce_intelligence.extraction import parse_extraction_response
from workforce_intelligence.records import normalize_finding


class LinkedInSourceTests(unittest.TestCase):
    def test_linkedin_extraction_keeps_original_direct_url(self):
        url = "https://www.linkedin.com/posts/example-company_workforce-activity-123"
        metadata = {
            "title": "Example Company post",
            "url": url,
            "source_platform": "LinkedIn",
            "industry": "Automotive manufacturing",
        }
        response = json.dumps({"findings": [{
            "problem_type": "Skilled worker shortage",
            "description": "The company reports difficulty hiring skilled production workers.",
            "supporting_quote": "difficulty hiring skilled production workers",
            "industry": "Automotive manufacturing",
            "source_url": "https://search.example/result",
        }]})
        rows = parse_extraction_response(
            response, metadata,
            source_text="The company reports difficulty hiring skilled production workers.",
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_url"], url)
        self.assertEqual(rows[0]["source_platform"], "LinkedIn")

    def test_linkedin_finding_rejects_missing_or_non_linkedin_url(self):
        with self.assertRaises(ValueError):
            normalize_finding({
                "problem_type": "Hiring shortage",
                "description": "The company cannot fill roles.",
                "source_platform": "LinkedIn",
                "source_url": "https://search.example/linkedin-result",
            })
        with self.assertRaises(ValueError):
            normalize_finding({
                "problem_type": "Hiring shortage",
                "description": "The company cannot fill roles.",
                "source_platform": "LinkedIn",
                "source_url": None,
            })

    def test_web_finding_schema_remains_backward_compatible(self):
        row = normalize_finding({
            "problem_type": "Hiring shortage",
            "description": "The company cannot fill roles.",
            "source_url": "https://example.org/report",
        })
        self.assertEqual(row["source_platform"], None)
        self.assertEqual(row["source_url"], "https://example.org/report")


if __name__ == "__main__":
    unittest.main()
