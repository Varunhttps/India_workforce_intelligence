import unittest
from unittest.mock import patch

from frontend.data_loader import TABS, read_workforce_sheets


class DashboardSheetReaderTests(unittest.TestCase):
    def test_dashboard_reader_lists_six_expected_tabs(self):
        self.assertEqual(len(TABS), 6)
        self.assertEqual(
            TABS,
            [
                "Source Register",
                "Market Research",
                "Market Insights & Trends",
                "Product Feature Opportunities",
                "Weekly Trends",
                "Opportunity Changes",
            ],
        )

    def test_missing_credentials_fail_with_clear_message(self):
        with patch.dict("os.environ", {"GOOGLE_SHEET_ID": "", "GOOGLE_SERVICE_ACCOUNT_JSON": ""}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "Google Sheets credentials are not configured"):
                read_workforce_sheets(spreadsheet_id=None, service_account_json=None)


if __name__ == "__main__":
    unittest.main()
