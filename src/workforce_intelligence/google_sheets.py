"""Publish each research run into one persistent Google spreadsheet."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from typing import Any

import gspread

from .records import FINDING_COLUMNS, SOURCE_COLUMNS, deduplicate_findings

HISTORY_COLUMNS = FINDING_COLUMNS + ["history_status", "first_seen", "last_seen", "occurrences"]

SHEET_HEADERS = {
    "Run Overview": ["Metric", "Value"],
    "Workforce Findings": ["Research ID"] + FINDING_COLUMNS,
    "New Findings": ["Research ID"] + HISTORY_COLUMNS,
    "Recurring Findings": ["Research ID"] + HISTORY_COLUMNS,
    "Source Register": [
        "Source ID", "Source Title", "Source URL", "Source Type",
        "Publisher / Author", "Industry", "Publication Date", "Access Date",
        "Source Credibility", "Key Information", "Related Research IDs",
        "Collection Status", "Relevance Status", "Verification Status", "Review Notes",
    ],
    "Research Summary": ["Industry", "Country", "Problem Type", "Finding Count"],
}


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:10].upper()
    return f"{prefix}-{digest}"


def _cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def build_sheet_payloads(findings, sources, new_findings=None, recurring_findings=None):
    """Build deterministic tab payloads; IDs remain stable across weekly runs."""
    normalized = deduplicate_findings(findings)
    research_ids = {
        id(row): _stable_id("FND", "|".join(str(row.get(k) or "") for k in
                    ("source_url", "problem_type", "description")))
        for row in normalized
    }

    def finding_rows(rows, include_history=False):
        output = []
        for raw in rows or []:
            row = dict(raw)
            identity = _stable_id("FND", "|".join(str(row.get(k) or "") for k in
                               ("source_url", "problem_type", "description")))
            fields = HISTORY_COLUMNS if include_history else FINDING_COLUMNS
            output.append([identity] + [_cell(row.get(col)) for col in fields])
        return output

    by_url = {}
    for row in normalized:
        by_url.setdefault(row.get("source_url"), []).append(research_ids[id(row)])

    source_rows = []
    for source in sources or []:
        url = source.get("Source URL") or ""
        related = by_url.get(url, [])
        source_rows.append([
            _stable_id("SRC", url or str(source.get("Source title") or "")),
            _cell(source.get("Source title")),
            _cell(url),
            _cell(source.get("Source platform") or "Website"),
            "",  # Publisher / author is left blank unless explicitly identified.
            _cell(source.get("Industry searched")),
            _cell(source.get("Publication date")),
            date.today().isoformat(),
            "Pending review",
            "; ".join(str(item.get("description") or "") for item in normalized
                      if item.get("source_url") == url),
            ", ".join(related),
            _cell(source.get("Collection status")),
            _cell(source.get("Relevance status")),
            _cell(source.get("Verification status")),
            _cell(source.get("Review notes")),
        ])

    summary = {}
    for row in normalized:
        key = (row.get("industry") or "", row.get("country") or "", row.get("problem_type") or "")
        summary[key] = summary.get(key, 0) + 1

    run_overview = [
        ["Findings extracted", len(normalized)],
        ["New findings", len(new_findings or [])],
        ["Recurring findings", len(recurring_findings or [])],
        ["Sources discovered", len(sources or [])],
        ["Sources collected", sum(1 for s in (sources or []) if s.get("Collection status") == "Collected")],
        ["LinkedIn sources discovered", sum(1 for s in (sources or []) if s.get("Source platform") == "LinkedIn")],
    ]
    return {
        "Run Overview": [SHEET_HEADERS["Run Overview"]] + run_overview,
        "Workforce Findings": [SHEET_HEADERS["Workforce Findings"]] + finding_rows(normalized),
        "New Findings": [SHEET_HEADERS["New Findings"]] + finding_rows(new_findings, True),
        "Recurring Findings": [SHEET_HEADERS["Recurring Findings"]] + finding_rows(recurring_findings, True),
        "Source Register": [SHEET_HEADERS["Source Register"]] + source_rows,
        "Research Summary": [SHEET_HEADERS["Research Summary"]] + [
            list(key) + [count] for key, count in sorted(summary.items())
        ],
    }


def publish_to_google_sheets(findings, sources, spreadsheet_id=None,
                             service_account_json=None, new_findings=None,
                             recurring_findings=None):
    """Replace tab contents in the configured spreadsheet; do not create weekly copies."""
    spreadsheet_id = spreadsheet_id or os.getenv("GOOGLE_SHEET_ID")
    service_account_json = service_account_json or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not spreadsheet_id or not service_account_json:
        raise RuntimeError("Set GOOGLE_SHEET_ID and GOOGLE_SERVICE_ACCOUNT_JSON to publish Google Sheets.")

    credentials = json.loads(service_account_json)
    client = gspread.service_account_from_dict(credentials)
    spreadsheet = client.open_by_key(spreadsheet_id)
    payloads = build_sheet_payloads(findings, sources, new_findings, recurring_findings)

    for title, values in payloads.items():
        try:
            worksheet = spreadsheet.worksheet(title)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=title, rows=max(len(values), 100), cols=max(len(values[0]), 15))
        worksheet.clear()
        worksheet.resize(rows=max(len(values), 1), cols=max(len(values[0]), 1))
        worksheet.update(range_name="A1", values=values)
        worksheet.freeze(rows=1)
    return spreadsheet.url
