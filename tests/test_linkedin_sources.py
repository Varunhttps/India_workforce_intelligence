import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from openpyxl import load_workbook
from workforce_intelligence.pipeline import run_research

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

    def test_pipeline_carries_linkedin_url_into_workbook(self):
        linkedin_url = "https://www.linkedin.com/posts/example-company_workforce-activity-123"

        class FakeExtractor:
            def extract(self, text, source):
                return [{"problem_type": "Skilled worker shortage", "description": "Difficulty hiring production workers.", "source_url": "https://search.example/rewritten-url"}]

        with TemporaryDirectory() as tmp:
            document = Path(tmp) / "public_post.txt"
            document.write_text("Public post text with sufficient length for extraction.", encoding="utf-8")
            with patch("workforce_intelligence.pipeline.discover_sources", return_value=[{"title": "Company LinkedIn post", "url": linkedin_url, "source_platform": "LinkedIn", "industry": "Automotive manufacturing"}]), patch("workforce_intelligence.pipeline.collect_document", return_value={"local_path": str(document)}):
                result = run_research(output_dir=tmp, extractor=FakeExtractor())
            self.assertEqual(result["findings"][0]["source_url"], linkedin_url)
            self.assertEqual(result["findings"][0]["source_platform"], "LinkedIn")
            workbook = load_workbook(result["workbook_path"], read_only=True)
            sheet = workbook["Workforce Findings"]
            headers = [cell.value for cell in sheet[1]]
            row = dict(zip(headers, [cell.value for cell in sheet[2]]))
            self.assertEqual(row["source_url"], linkedin_url)
            self.assertEqual(row["source_platform"], "LinkedIn")
            source_sheet = workbook["Source Register"]
            source_headers = [cell.value for cell in source_sheet[1]]
            source_row = dict(zip(source_headers, [cell.value for cell in source_sheet[2]]))
            self.assertEqual(source_row["Source URL"], linkedin_url)
            self.assertEqual(source_row["Source platform"], "LinkedIn")
            workbook.close()


if __name__ == "__main__":
    unittest.main()
