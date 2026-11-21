import unittest
from workforce_intelligence.google_sheets import build_sheet_payloads, SHEET_HEADERS


class GoogleSheetsPayloadTests(unittest.TestCase):
    def test_six_manager_tabs_and_linked_source_register(self)
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
            "Candidate source class (domain heuristic)": "Intergovernmental / multilateral (heuristic)",
        }]
        payloads = build_sheet_payloads(findings, sources)
        self.assertEqual(set(payloads), set(SHEET_HEADERS))
        self.assertEqual(len(payloads), 6)
        headers = payloads["Source Register"][0]
        row = dict(zip(headers, payloads["Source Register"][1]))
        self.assertEqual(row["Source URL"], url)
        self.assertEqual(row["Source Type"], "LinkedIn")
        self.assertEqual(row["Source Credibility Assessment"], "Limited — user-generated content; treated as a supporting signal only")
        self.assertTrue(row["Source ID"].startswith("SRC-"))
        self.assertTrue(row["Related Research IDs"].startswith("RES-"))
        research = payloads["Market Research"]
        self.assertEqual(research[1][1], row["Source ID"])
        research_row = dict(zip(research[0], research[1]))
        self.assertEqual(research_row["Source URL"], url)
        self.assertEqual(research_row["Weekly Status"], "New this week")
        self.assertTrue(research_row["First Seen"])
        self.assertIn("Business Impact", research_row)
        self.assertIn("Publication Date", research_row)
        self.assertNotIn("Evidence / Supporting Information", research_row)
        self.assertNotIn("Research Status", research_row)
        self.assertNotIn("Verification Status", row)
        self.assertNotIn("Review Notes", row)
        self.assertTrue(payloads["Product Feature Opportunities"][1][0].startswith("OPP-"))
        self.assertTrue(any(r[1] == "Industry Summary"
                            for r in payloads["Market Insights & Trends"][1:]))
        self.assertNotIn("Interpretation Status", payloads["Market Insights & Trends"][0])
        self.assertNotIn("Review Status", payloads["Product Feature Opportunities"][0])

    def test_empty_run_still_returns_four_headers(self):
        payloads = build_sheet_payloads([], [])
        self.assertEqual(set(payloads), set(SHEET_HEADERS))
        self.assertTrue(all(len(rows) == 1 for rows in payloads.values()))

    def test_industry_summary_aggregates_distinct_problems_and_sources(self):
        findings = [
            {"problem_type": "Skilled worker shortage", "description": "Shortage at plant A",
             "industry": "Automotive", "source_url": "https://example.com/a", "country": "Germany"},
            {"problem_type": "skilled   worker shortage", "description": "Shortage at plant B",
             "industry": "Automotive", "source_url": "https://example.com/b", "country": "Germany"},
            {"problem_type": "Employee attrition", "description": "High turnover at plant C",
             "industry": "Automotive", "source_url": "https://example.com/c", "country": "India"},
        ]
        payloads = build_sheet_payloads(findings, [])
        rows = payloads["Market Insights & Trends"]
        self.assertEqual(len(rows), 2)
        summary = dict(zip(rows[0], rows[1]))
        self.assertEqual(summary["Distinct Problem Count"], 2)
        self.assertEqual(summary["Supporting Source Count"], 3)
        self.assertEqual(summary["Countries"], "Germany, India")
        self.assertNotIn("Interpretation Status", rows[0])

    def test_opportunity_mapping_varies_and_priority_uses_evidence_breadth(self):
        findings = [
            {"problem_type": "Employee attrition", "description": "High turnover",
             "industry": "Automotive", "source_url": "https://example.com/a"},
            {"problem_type": "Skills gap", "description": "Missing technical skills",
             "industry": "Automotive", "source_url": "https://example.com/b"},
            {"problem_type": "Payroll cost pressure", "description": "Rising payroll costs",
             "industry": "Automotive", "source_url": "https://example.com/c"},
        ]
        payloads = build_sheet_payloads(findings, [])
        rows = payloads["Product Feature Opportunities"]
        self.assertEqual(len(rows), 4)
        self.assertEqual(len({r[4] for r in rows[1:]}), 3)
        self.assertEqual(len({r[5] for r in rows[1:]}), 3)
        self.assertIn("High", {r[7] for r in rows[1:]})
        self.assertIn("Low", {r[7] for r in rows[1:]})
        self.assertNotIn("Review Status", rows[0])

    def test_historical_findings_are_retained_in_cumulative_payload(self):
        history = [{
            "problem_type": "Payroll forecasting gap",
            "description": "Old historical finding",
            "industry": "Industrial manufacturing",
            "source_name": "Prior report",
            "source_url": "https://example.com/old",
            "source_platform": "Web",
            "country": "Germany",
            "first_seen": "2026-11-02", "last_seen": "2026-11-09",
            "first_seen_week": "2026-11-02", "last_seen_week": "2026-11-09",
            "weeks_seen": ["2026-11-02", "2026-11-09"], "occurrences": 2,
        }]
        payloads = build_sheet_payloads([], [], history_records=history)
        self.assertEqual(len(payloads["Market Research"]), 2)
        history_row = dict(zip(payloads["Market Research"][0], payloads["Market Research"][1]))
        self.assertEqual(history_row["Source URL"], "https://example.com/old")
        self.assertEqual(history_row["Weekly Status"], "Last seen before this week")
        self.assertEqual(history_row["Occurrences"], 2)
        self.assertEqual(len(payloads["Source Register"]), 2)


    def test_weekly_trends_and_opportunity_changes_tabs(self):
        history = [
            {
                "problem_type": "Skills gap",
                "description": "Missing technical skills at factory",
                "industry": "Manufacturing",
                "source_name": "Report A",
                "source_url": "https://example.org/a",
                "source_platform": "Web",
                "country": "Germany",
                "first_seen": "2026-11-10",
                "last_seen": "2026-11-17",
                "first_seen_week": "2026-11-09",
                "last_seen_week": "2026-11-16",
                "weeks_seen": ["2026-11-09", "2026-11-16"],
                "occurrences": 2,
            },
            {
                "problem_type": "Skills gap",
                "description": "Missing technical skills at another factory",
                "industry": "Manufacturing",
                "source_name": "Report B",
                "source_url": "https://example.org/b",
                "source_platform": "Web",
                "country": "France",
                "first_seen": "2026-11-17",
                "last_seen": "2026-11-17",
                "first_seen_week": "2026-11-16",
                "last_seen_week": "2026-11-16",
                "weeks_seen": ["2026-11-16"],
                "occurrences": 1,
            },
        ]
        payloads = build_sheet_payloads([], [], research_date="2026-11-21", history_records=history)
        trend = dict(zip(payloads["Weekly Trends"][0], payloads["Weekly Trends"][1]))
        self.assertEqual(trend["Signal Status"], "Active this week")
        self.assertEqual(trend["Sources This Week"], 2)
        self.assertEqual(trend["Sources Previous Week"], 1)
        self.assertTrue(trend["Potentially Worsening"])
        self.assertIn("Potentially worsening", trend["Signal Momentum"])

        changes = payloads["Opportunity Changes"]
        self.assertEqual(len(changes), 2)
        opportunity = dict(zip(changes[0], changes[1]))
        self.assertEqual(opportunity["Change Status"], "Expanded evidence")
        self.assertEqual(opportunity["Sources This Week"], 2)
        self.assertEqual(opportunity["Sources Previous Week"], 1)
        self.assertEqual(opportunity["Priority"], "High")

if __name__ == "__main__":
    unittest.main()
