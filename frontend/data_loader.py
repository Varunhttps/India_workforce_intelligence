"""Reusable Google Sheets reader for the Streamlit frontend."""
import json
import os
import gspread
import pandas as pd

TABS = ["Source Register", "Market Research", "Market Insights & Trends", "Product Feature Opportunities", "Weekly Trends", "Opportunity Changes"]


def read_workforce_sheets(spreadsheet_id=None, service_account_json=None):
    spreadsheet_id = spreadsheet_id or os.getenv("GOOGLE_SHEET_ID")
    service_account_json = service_account_json or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not spreadsheet_id or not service_account_json:
        raise RuntimeError("Google Sheets credentials are not configured.")
    client = gspread.service_account_from_dict(json.loads(service_account_json))
    spreadsheet = client.open_by_key(spreadsheet_id)
    return {name: pd.DataFrame(spreadsheet.worksheet(name).get_all_records()) for name in TABS}, spreadsheet.url
