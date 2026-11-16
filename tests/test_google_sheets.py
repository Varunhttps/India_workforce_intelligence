import unittest
from workforce_intelligence.google_sheets import build_sheet_payloads


class GoogleSheetsPayloadTests(unittest.TestCase):
    def test_source_register_matches_requested_fields_and_links_research(self):
        url = "https://www.linkedin.com/posts/example-company_workforce-activity-123"
        findings = [{
            "problem_type": "Skilled worker shortage",
            "description": "Difficulty hiring production workers.",
            "industry": "Automotive manufacturing",
            "source_name": "Company post",
            "source_url": url,
            "source_platform": "LinkedIn",
        }]
        sources = [{
            "Source title": "Company post",
            "Source URL": url,
            "Source platform": "LinkedIn",
            "Industry searched": "Automotive manufacturing",
            "Collection status": "Collected",
            "Relevance status": "Findings extracted",
            "Verification status": "Not verified",
        }]
        payloads = build_sheet_payloads(findings, sources)
        headers = payloads["Source Register"][0]
        row = dict(zip(headers, payloads["Source Register"][1]))
        self.assertEqual(row["Source URL"], url)
        self.assertEqual(row["Source Type"], "LinkedIn")
        self.assertEqual(row["Source Credibility"], "Pending review")
        self.assertTrue(row["Source ID"].startswith("SRC-"))
        self.assertTrue(row["Related Research IDs"].startswith("FND-"))
        self.assertIn("Workforce Findings", payloads)
        self.assertIn("Run Overview", payloads)


if __name__ == "__main__":
    unittest.main()
