import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from openpyxl import load_workbook
from workforce_intelligence.pipeline import run_research

class FakeExtractor:
    def extract(self, text, source):
        return [{"problem_type": "Labour shortage", "description": "Unfilled production roles.", "country": "Germany", "region": "Bavaria", "publication_date": "2026-08", "source_name": source["title"], "source_url": source["url"]}]

class PipelineTests(unittest.TestCase):
    @patch("workforce_intelligence.pipeline.discover_sources", return_value=[])
    def test_empty_discovery_does_not_require_gemini_key(self, discover):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_research(output_dir=tmp)
            self.assertEqual(result["sources_discovered"], 0)
            self.assertTrue(Path(result["workbook_path"]).exists())

    @patch("workforce_intelligence.pipeline.collect_document")
    @patch("workforce_intelligence.pipeline.discover_sources")
    def test_end_to_end_export_separates_search_date(self, discover, collect):
        with tempfile.TemporaryDirectory() as tmp:
            document = Path(tmp) / "source.txt"
            document.write_text("Source text for a test report.", encoding="utf-8")
            discover.return_value = [{"title": "Manufacturing workforce report", "url": "https://example.org/report", "industry": "Automotive manufacturing", "country_searched": None, "search_published_date": "2026-09-10"}]
            collect.return_value = {"local_path": str(document)}
            result = run_research(output_dir=tmp, extractor=FakeExtractor())
            self.assertEqual(result["findings_extracted"], 1)
            workbook = load_workbook(result["workbook_path"], read_only=True)
            sheet = workbook["Source Register"]
            headers = [cell.value for cell in sheet[1]]
            row = dict(zip(headers, [cell.value for cell in sheet[2]]))
            self.assertEqual(row["Publication date"], "2026-08")
            self.assertEqual(row["Search result date"], "2026-09-10")
            self.assertEqual(row["Actual geographic scope"], "Germany")
            self.assertEqual(row["Region"], "Bavaria")
            self.assertEqual(row["Verification status"], "Not verified")
            workbook.close()

if __name__ == "__main__":
    unittest.main()
