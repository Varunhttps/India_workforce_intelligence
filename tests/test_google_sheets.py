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
        research_row = dict(zip(research[0], research[1]))
        self.assertEqual(research_row["Source URL"], url)
        self.assertEqual(research_row["Weekly Status"], "New this week")
        self.assertEqual(research_row["First Seen"], "")
        self.assertTrue(payloads["Product Feature Opportunities"][1][0].startswith("OPP-"))
        self.assertTrue(any(r[1] == "Consolidated Workforce Challenges"
                            for r in payloads["Market Insights & Trends"][1:]))

    def test_empty_run_still_returns_four_headers(self):
        payloads = build_sheet_payloads([], [])
        self.assertEqual(set(payloads), set(SHEET_HEADERS))
        self.assertTrue(all(len(rows) == 1 for rows in payloads.values()))

    def test_distinct_problem_count_is_not_source_count(self):
        findings = [
            {"problem_type": "Skilled worker shortage", "description": "Shortage at plant A",
             "industry": "Automotive", "source_url": "https://example.com/a"},
            {"problem_type": "skilled   worker shortage", "description": "Shortage at plant B",
             "industry": "Automotive", "source_url": "https://example.com/b"},
        ]
        payloads = build_sheet_payloads(findings, [])
        rows = payloads["Market Insights & Trends"]
        insight = next(row for row in rows[1:] if row[1] == "Consolidated Workforce Challenges")
        self.assertEqual(insight[4], 1)
        self.assertEqual(insight[5], 2)

    def test_historical_findings_are_retained_in_cumulative_payload(self):
        history = [{
            "problem_type": "Payroll forecasting gap",
            "description": "Old historical finding",
            "industry": "Industrial manufacturing",
            "source_name": "Prior report",
            "source_url": "https://example.com/old",
            "source_platform": "Web",
            "country": "Germany",
            "first_seen": "2026-11-09", "last_seen": "2026-11-16",
            "first_seen_week": "2026-11-09", "last_seen_week": "2026-11-16",
            "weeks_seen": ["2026-11-09", "2026-11-16"], "occurrences": 2,
        }]
        payloads = build_sheet_payloads([], [], history_records=history)
        self.assertEqual(len(payloads["Market Research"]), 2)
        history_row = dict(zip(payloads["Market Research"][0], payloads["Market Research"][1]))
        self.assertEqual(history_row["Source URL"], "https://example.com/old")
        self.assertEqual(history_row["Weekly Status"], "Not observed this week")
        self.assertEqual(history_row["Occurrences"], 2)
        self.assertEqual(len(payloads["Source Register"]), 2)


if __name__ == "__main__":
    unittest.main()
