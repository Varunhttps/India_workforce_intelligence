import unittest
from workforce_intelligence.google_sheets import build_sheet_payloads, SHEET_HEADERS


class GoogleSheetsPayloadTests(unittest.TestCase):
    def test_five_manager_tabs_and_linked_source_register(self):
        url = "https://www.linkedin.com/posts/example-company_workforce-activity-123"
        findings = [{
            "problem_type": "Skilled worker shortage",
            "description": "Difficulty hiring production workers.",
            "industry": "Automotive manufacturing",
            "source_name": "Company post",
            "source_url": url,
            "source_platform": "LinkedIn",
            "country": "India", "sub_industry": "EV manufacturing",
        }]
        sources = [{
            "Source title": "Company post", "Source URL": url,
            "Source platform": "LinkedIn", "Industry searched": "Automotive manufacturing",
            "Collection status": "Collected", "Relevance status": "Findings extracted",
            "Candidate source class (domain heuristic)": "Intergovernmental / multilateral (heuristic)",
        }]
        payloads = build_sheet_payloads(findings, sources)
        self.assertEqual(set(payloads), set(SHEET_HEADERS))
        self.assertIn("Weekly Trends", payloads)
        self.assertNotIn("Opportunity Changes", payloads)
        self.assertNotIn("Opportunity Changes", SHEET_HEADERS)
        self.assertEqual(len(payloads), 5)
        trend_headers = payloads["Weekly Trends"][0]
        self.assertEqual(trend_headers, ["Trend ID", "Industry", "Workforce Problem", "Supporting Sources", "Weeks Seen", "Latest Evidence Date"])
        trend = dict(zip(trend_headers, payloads["Weekly Trends"][1]))
        self.assertEqual(trend["Weeks Seen"], 1)
        self.assertIsInstance(trend["Weeks Seen"], int)
        self.assertNotIn("First Seen", trend)
        self.assertNotIn("Latest Week", trend)
        headers = payloads["Source Register"][0]
        row = dict(zip(headers, payloads["Source Register"][1]))
        self.assertEqual(row["Source URL"], url)
        self.assertEqual(row["Source Type"], "LinkedIn")
        self.assertEqual(row["Sub-industry"], "EV manufacturing")
        self.assertEqual(row["Sub-industry"], "EV manufacturing")
        self.assertNotIn("Source Credibility Assessment", row)
        self.assertNotIn("Relevance Status", row)
        self.assertTrue(row["Source ID"].startswith("SRC-"))
        self.assertTrue(row["Related Research IDs"].startswith("RES-"))
        research = payloads["Market Research"]
        self.assertEqual(research[1][1], row["Source ID"])
        research_row = dict(zip(research[0], research[1]))
        self.assertEqual(research_row["Source URL"], url)
        self.assertNotIn("Weekly Status", research_row)
        self.assertTrue(research_row["First Seen"])
        self.assertNotIn("Business Impact", research_row)
        self.assertNotIn("Publication Date", research_row)
        self.assertIn("First Seen", research_row)
        self.assertIn("Latest Week", research_row)
        self.assertNotIn("Last Seen", research_row)
        self.assertNotIn("Weeks Seen", research_row)
        self.assertIn("Observation Weeks", research_row)
        self.assertNotIn("Evidence / Supporting Information", research_row)
        self.assertNotIn("Research Status", research_row)
        self.assertNotIn("Verification Status", row)
        self.assertNotIn("Review Notes", row)
        self.assertTrue(payloads["Product Feature Opportunities"][1][0].startswith("OPP-"))
        self.assertTrue(any(r[1] == "Industry Summary"
                            for r in payloads["Market Insights & Trends"][1:]))
        self.assertNotIn("Interpretation Status", payloads["Market Insights & Trends"][0])
        self.assertNotIn("Review Status", payloads["Product Feature Opportunities"][0])
        self.assertIn("Last Updated", payloads["Product Feature Opportunities"][0])
        self.assertIn("Latest Evidence Date", payloads["Market Insights & Trends"][0])
        self.assertIn("Latest Evidence Date", payloads["Weekly Trends"][0])

    def test_source_register_subindustry_and_dates_are_formatted(self):
        url = "https://example.com/published"
        findings = [{
            "problem_type": "Skills gap", "description": "Example evidence",
            "industry": "Manufacturing", "sub_industry": "Electronics",
            "source_url": url, "country": "India", "sub_industry": "EV manufacturing",
        }]
        sources = [{
            "Source title": "Original article title", "Source URL": url,
            "Source platform": "Web", "Industry searched": "Manufacturing",
            "Publication date": "2026-11-20", "Access Date": "2026-11-28",
        }]
        payloads = build_sheet_payloads(findings, sources, research_date="2026-11-28")
        source_row = dict(zip(payloads["Source Register"][0], payloads["Source Register"][1]))
        self.assertEqual(source_row["Sub-industry"], "Electronics")
        self.assertEqual(source_row["Related Research IDs"].startswith("RES-"), True)
        self.assertEqual(source_row["Publication Date"], "20112026")
        self.assertEqual(source_row["Access Date"], "28112026")
        research_row = dict(zip(payloads["Market Research"][0], payloads["Market Research"][1]))
        self.assertEqual(research_row["Research Date"], "28112026")
        self.assertEqual(research_row["First Seen"], "28112026")
        self.assertEqual(research_row["Latest Week"], "23112026")

    def test_source_register_subindustry_and_dates_are_formatted(self):
        url = "https://example.com/published"
        findings = [{
            "problem_type": "Skills gap", "description": "Example evidence",
            "industry": "Manufacturing", "sub_industry": "Electronics",
            "source_url": url, "country": "India",
        }]
        sources = [{
            "Source title": "Original article title", "Source URL": url,
            "Source platform": "Web", "Industry searched": "Manufacturing",
            "Publication date": "2026-11-20", "Access Date": "2026-11-28",
        }]
        payloads = build_sheet_payloads(findings, sources, research_date="2026-11-28")
        source_row = dict(zip(payloads["Source Register"][0], payloads["Source Register"][1]))
        self.assertEqual(source_row["Sub-industry"], "Electronics")
        self.assertTrue(source_row["Related Research IDs"].startswith("RES-"))
        self.assertEqual(source_row["Publication Date"], "20112026")
        self.assertEqual(source_row["Access Date"], "28112026")
        research_row = dict(zip(payloads["Market Research"][0], payloads["Market Research"][1]))
        self.assertEqual(research_row["Research Date"], "28112026")
        self.assertEqual(research_row["First Seen"], "28112026")
        self.assertEqual(research_row["Latest Week"], "23112026")

    def test_market_research_exports_exact_observation_weeks_for_dashboard(self):
        history = [{
            "problem_type": "Skilled worker shortage",
            "description": "Difficulty hiring production workers.",
            "industry": "Automotive manufacturing",
            "source_name": "Historical report",
            "source_url": "https://example.com/historical",
            "source_platform": "Web",
            "country": "India",
            "first_seen": "2026-11-02", "last_seen": "2026-11-23",
            "first_seen_week": "2026-11-02", "last_seen_week": "2026-11-23",
            "weeks_seen": ["2026-11-02", "2026-11-09", "2026-11-23"],
            "occurrences": 3,
        }]
        payloads = build_sheet_payloads([], [], research_date="2026-11-23", history_records=history)
        headers, values = payloads["Market Research"][0], payloads["Market Research"][1]
        row = dict(zip(headers, values))
        self.assertEqual(row["Observation Weeks"], "2026-11-02, 2026-11-09, 2026-11-23")


    def test_empty_run_returns_five_headers_including_weekly_trends(self):
        payloads = build_sheet_payloads([], [])
        self.assertEqual(set(payloads), set(SHEET_HEADERS))
        self.assertIn("Weekly Trends", payloads)
        self.assertEqual(len(payloads), 5)
        self.assertEqual(payloads["Weekly Trends"], [["Trend ID", "Industry", "Workforce Problem", "Supporting Sources", "Weeks Seen", "Latest Evidence Date"]])
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

    def test_sheets_are_sorted_by_industry_and_insights_keep_history_dates_counts(self):
        current = [
            {"problem_type":"Worker shortage","description":"New current evidence","industry":"Zeta Manufacturing",
             "source_name":"Current","source_url":"https://example.com/z","country":"India"},
            {"problem_type":"Worker shortage","description":"Another current evidence","industry":"Alpha Logistics",
             "source_name":"Current","source_url":"https://example.com/a","country":"Germany"},
        ]
        history = [
            {"problem_type":"Worker shortage","description":"Historical finding","industry":"Alpha Logistics",
             "source_name":"Old","source_url":"https://example.com/old","country":"Germany",
             "first_seen":"2026-11-02","last_seen":"2026-11-16","first_seen_week":"2026-11-02",
             "last_seen_week":"2026-11-16","weeks_seen":["2026-11-02","2026-11-09","2026-11-16"],"occurrences":3},
        ]
        payloads = build_sheet_payloads(current, [], research_date="2026-11-23", history_records=history)
        for tab, industry_col in (("Market Research", 2), ("Product Feature Opportunities", 1),
                                  ("Market Insights & Trends", 2), ("Weekly Trends", 1)):
            industries = [row[industry_col] for row in payloads[tab][1:]]
            self.assertEqual(industries, sorted(industries, key=str.casefold))
        insights = payloads["Market Insights & Trends"]
        alpha = next(dict(zip(insights[0], row)) for row in insights[1:] if row[2] == "Alpha Logistics")
        self.assertGreaterEqual(alpha["Distinct Problem Count"], 1)
        self.assertEqual(alpha["Latest Evidence Date"], "23112026")

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
        self.assertNotIn("Weekly Status", history_row)
        self.assertNotIn("Occurrences", history_row)
        self.assertEqual(len(payloads["Source Register"]), 2)



if __name__ == "__main__":
    unittest.main()
