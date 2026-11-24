import tempfile
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from openpyxl import load_workbook
from workforce_intelligence.pipeline import run_research

class FakeExtractor:
    def extract(self, text, source):
        return [{"problem_type": "Labour shortage", "description": "Unfilled production roles.", "country": "Germany", "region": "Bavaria", "publication_date": "2026-08", "source_name": source["title"], "source_url": source["url"]}]

class DiagnosticExtractor:
    def extract(self, text, source):
        if source["title"].startswith("Fail"):
            raise RuntimeError("sensitive error detail should not be logged")
        return []

class PipelineTests(unittest.TestCase):
    @patch("workforce_intelligence.pipeline.publish_to_google_sheets", return_value="https://docs.google.com/spreadsheets/d/test")
    @patch("workforce_intelligence.pipeline.discover_sources", return_value=[])
    def test_google_sheets_publisher_receives_cumulative_history(self, discover, publish):
        with tempfile.TemporaryDirectory() as tmp:
            history = Path(tmp) / "history.jsonl"
            history.write_text(
                json.dumps({
                    "finding_key": "historical-payroll-gap",
                    "problem_type": "Payroll forecasting gap",
                    "description": "Historical finding",
                    "industry": "Manufacturing",
                    "source_name": "Old report",
                    "source_url": "https://example.org/old",
                }) + "\n",
                encoding="utf-8",
            )
            result = run_research(
                output_dir=tmp, history_path=str(history), publish_google_sheets=True,
                google_sheet_id="sheet-id", google_service_account_json="{}",
            )
            self.assertEqual(result["google_sheet_url"], "https://docs.google.com/spreadsheets/d/test")
            kwargs = publish.call_args.kwargs
            self.assertEqual(kwargs["history_records"][0]["problem_type"], "Payroll forecasting gap")
            self.assertIn("new_findings", kwargs)
            self.assertIn("recurring_findings", kwargs)
            self.assertIn("opportunity_changes", result)
            self.assertTrue(result["opportunity_changes"])

    @patch("workforce_intelligence.pipeline.discover_sources", return_value=[])
    def test_empty_discovery_does_not_require_gemini_key(self, discover):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_research(
                output_dir=tmp, history_path=str(Path(tmp) / "history.jsonl"),
                source_history_path=str(Path(tmp) / "sources.jsonl"),
            )
            self.assertEqual(result["sources_discovered"], 0)
            self.assertEqual(result["source_assessment_counts"], {
                "with_findings": 0, "no_findings": 0, "unable_to_assess": 0,
            })
            self.assertTrue(Path(result["workbook_path"]).exists())

    @patch("workforce_intelligence.pipeline.collect_document")
    @patch("workforce_intelligence.pipeline.discover_sources")
    def test_source_assessment_counts_distinguish_empty_from_failed(self, discover, collect):
        with tempfile.TemporaryDirectory() as tmp:
            document = Path(tmp) / "source.txt"
            document.write_text("Source text for a test report.", encoding="utf-8")
            discover.return_value = [
                {"title": "Fail report", "url": "https://failed.example/report", "industry": "Manufacturing"},
                {"title": "Empty report", "url": "https://empty.example/report", "industry": "Manufacturing"},
            ]
            collect.return_value = {"local_path": str(document)}
            with self.assertLogs("workforce_intelligence.pipeline", level="WARNING") as logs:
                result = run_research(
                    output_dir=tmp, extractor=DiagnosticExtractor(),
                    history_path=str(Path(tmp) / "history.jsonl"),
                    source_history_path=str(Path(tmp) / "sources.jsonl"),
                )
            self.assertEqual(result["source_assessment_counts"], {
                "with_findings": 0, "no_findings": 1, "unable_to_assess": 1,
            })
            self.assertEqual(result["sources"][0]["Relevance status"], "Unable to assess — extraction failed")
            self.assertEqual(result["sources"][1]["Relevance status"], "Not relevant — no qualifying workforce finding extracted")
            self.assertIn("RuntimeError", logs.output[0])
            self.assertIn("failed.example", logs.output[0])
            self.assertNotIn("sensitive error detail", logs.output[0])

    @patch("workforce_intelligence.pipeline.collect_document")
    @patch("workforce_intelligence.pipeline.discover_sources")
    def test_end_to_end_export_separates_search_date(self, discover, collect):
        with tempfile.TemporaryDirectory() as tmp:
            document = Path(tmp) / "source.txt"
            document.write_text("Source text for a test report.", encoding="utf-8")
            discover.return_value = [{"title": "Manufacturing workforce report", "url": "https://example.org/report", "industry": "Automotive manufacturing", "country_searched": None, "search_published_date": "2026-09-10"}]
            collect.return_value = {"local_path": str(document)}
            result = run_research(
                output_dir=tmp, extractor=FakeExtractor(),
                history_path=str(Path(tmp) / "history.jsonl"),
                source_history_path=str(Path(tmp) / "sources.jsonl"),
            )
            self.assertEqual(result["findings_extracted"], 1)
            self.assertEqual(result["source_assessment_counts"], {
                "with_findings": 1, "no_findings": 0, "unable_to_assess": 0,
            })
            self.assertIn("opportunity_changes", result)
            workbook = load_workbook(result["workbook_path"], read_only=True)
            self.assertIn("Weekly Trends", workbook.sheetnames)
            self.assertNotIn("Opportunity Changes", workbook.sheetnames)
            sheet = workbook["Source Register"]
            headers = [cell.value for cell in sheet[1]]
            row = dict(zip(headers, [cell.value for cell in sheet[2]]))
            self.assertEqual(row["Publication date"], "2026-08")
            self.assertEqual(row["Search result date"], "2026-09-10")
            self.assertEqual(row["Actual geographic scope"], "Germany")
            self.assertEqual(row["Region"], "Bavaria")
            self.assertNotIn("Verification status", row)
            self.assertNotIn("Review Notes", row)
            self.assertEqual(row["Relevance status"], "Relevant — workforce findings extracted")
            workbook.close()

if __name__ == "__main__":
    unittest.main()
