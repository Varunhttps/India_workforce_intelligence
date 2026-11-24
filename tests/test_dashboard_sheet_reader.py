import unittest
from unittest.mock import patch, Mock

from frontend.data_loader import TABS, read_workforce_sheets


class DashboardSheetReaderTests(unittest.TestCase):
    def test_dashboard_reader_lists_five_expected_tabs(self):
        self.assertEqual(len(TABS), 5)
        self.assertEqual(
            TABS,
            [
                "Source Register",
                "Market Research",
                "Market Insights & Trends",
                "Product Feature Opportunities",
                "Weekly Trends",
            ],
        )

    def test_missing_credentials_fail_with_clear_message(self):
        with patch.dict("os.environ", {"GOOGLE_SHEET_ID": "", "GOOGLE_SERVICE_ACCOUNT_JSON": ""}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "Google Sheets credentials are not configured"):
                read_workforce_sheets(spreadsheet_id=None, service_account_json=None)

    def test_invalid_credentials_json_fail_with_safe_message(self):
        with self.assertRaisesRegex(RuntimeError, "Google service-account credentials contain invalid JSON"):
            read_workforce_sheets(spreadsheet_id="sheet-id", service_account_json="{not-json")

    def test_reader_loads_all_tabs_using_mocked_google_client(self):
        worksheet = Mock()
        worksheet.get_all_records.return_value = [{"Column": "value"}]
        spreadsheet = Mock()
        spreadsheet.worksheet.return_value = worksheet
        spreadsheet.url = "https://docs.google.com/spreadsheets/d/fake-sheet-id"
        client = Mock()
        client.open_by_key.return_value = spreadsheet
        with patch("frontend.data_loader.gspread.service_account_from_dict", return_value=client) as auth:
            data, url = read_workforce_sheets(
                spreadsheet_id="fake-sheet-id",
                service_account_json='{"type":"service_account"}',
            )
        auth.assert_called_once_with({"type": "service_account"})
        client.open_by_key.assert_called_once_with("fake-sheet-id")
        self.assertEqual(list(data.keys()), TABS)
        self.assertTrue(all(frame.to_dict("records") == [{"Column": "value"}] for frame in data.values()))
        self.assertEqual(url, spreadsheet.url)


if __name__ == "__main__":
    unittest.main()
