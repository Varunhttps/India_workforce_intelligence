import unittest
from workforce_intelligence.google_sheets import build_sheet_payloads, SHEET_HEADERS


class GoogleSheetsPayloadTests(unittest.TestCase):
    def test_four_manager_tabs_and_linked_source_register(self):
        url = "https://www.linkedin.com/posts/example-company_workforce-activity-123"
        findings = [{
            "problem_type": "Skilled worker shortage",
            "description": "Difficulty hiring production workers.",
            "industry": "Automotive manufacturing",
            "source_name": "Company post",
            "source_url": url,
            "source_platform": "LinkedIn",
            "country": "India",
        }]
        sources = [{
            "Source title": "Company post", "Source URL": url,
            "Source platform": "LinkedIn", "Industry searched": "Automotive manufacturing",
            "Collection status": "Collected", "Relevance status": "Findings extracted",
            "Verification status": "Not verified",
        }]
        payloads = build_sheet_payloads(findings, sources)
        self.assertEqual(set(payloads), set(SHEET_HEADERS))
        self.assertEqual(len(payloads), 4)
        headers = payloads["Source Register"][0]
        row = dict(zip(headers, payloads["Source Register"][1]))
        self.assertEqual(row["Source URL"], url)
        self.assertEqual(row["Source Type"], "LinkedIn")
        self.assertEqual(row["Source Credibility"], "Pending review")
        self.assertTrue(row["Source ID"].startswith("SRC-"))
        self.assertTrue(row["Related Research IDs"].startswith("RES-"))
        research = payloads["Market Research"]
        self.assertEqual(research[1][1], row["Source ID"])
        self.assertEqual(research[1][-1], url)
        self.assertTrue(payloads["Product Feature Opportunities"][1][0].startswith("OPP-"))
        self.assertTrue(any(r[1] == "Consolidated Workforce Challenges"
                            for r in payloads["Market Insights & Trends"][1:]))

    def test_empty_run_still_returns_four_headers(self):
        payloads = build_sheet_payloads([], [])
        self.assertEqual(set(payloads), set(SHEET_HEADERS))
        self.assertTrue(all(len(rows) == 1 for rows in payloads.values()))


if __name__ == "__main__":
    unittest.main()
