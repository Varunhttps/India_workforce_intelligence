"""Publish cumulative and week-aware workforce intelligence to Google Sheets."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from typing import Any

import gspread

from .history import week_start
from .records import deduplicate_findings

SHEET_HEADERS = {
    "Source Register": [
        "Source ID", "Source Title", "Source URL", "Source Type",
        "Publisher / Author", "Industry", "Publication Date", "Access Date",
        "Source Credibility", "Key Information", "Related Research IDs",
        "Collection Status", "Relevance Status", "Verification Status", "Review Notes",
    ],
    "Market Research": [
        "Research ID", "Source ID", "Industry", "Sub-industry",
        "Workforce Planning Area", "Identified Problem", "Problem Description",
        "Business Impact", "Evidence / Supporting Information", "Research Date",
        "Research Status", "Country", "Region", "Source URL",
        "First Seen", "Last Seen", "Weeks Seen", "Weekly Status",
    ],
    "Market Insights & Trends": [
        "Insight ID", "Section", "Industry", "Insight / Challenge",
        "Distinct Problem Count", "Supporting Source Count", "Related Research IDs",
        "Countries", "Research Date", "Interpretation Status",
    ],
    "Product Feature Opportunities": [
        "Opportunity ID", "Industry", "Identified Market Problem", "Market Need",
        "Proposed Product Capability", "Suggested Feature & Description",
        "Expected Business Value", "Priority", "Related Research IDs",
        "Supporting Source URLs", "Review Status",
    ],
}


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:10].upper()
    return f"{prefix}-{digest}"


def _cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(v) for v in value)
    return str(value)


def _identity(row: dict) -> str:
    return "|".join(str(row.get(k) or "").strip().casefold()
                    for k in ("industry", "problem_type", "description", "country"))


def _opportunity(row: dict) -> dict | None:
    """Conservative rules map reported needs to Nexplan's stated planning capabilities."""
    text = " ".join(str(row.get(k) or "") for k in ("problem_type", "description")).casefold()
    mappings = [
        (("headcount", "workforce allocation", "overstaff", "understaff", "staffing level"),
         "Workforce planning and allocation", "Workforce capacity and headcount planning",
         "Plan headcount and allocate workforce capacity across teams and sites."),
        (("skill", "talent", "retention", "attrition", "vacancy", "recruit", "hiring"),
         "Talent acquisition and workforce planning", "Skills, hiring and retention planning",
         "Connect hiring demand, skills gaps and retention assumptions to workforce plans."),
        (("payroll", "compensation", "benefit", "salary", "wage"),
         "Compensation and financial planning", "Compensation and payroll forecasting",
         "Forecast compensation, benefits and payroll costs alongside workforce plans."),
        (("capacity", "productivity", "resource", "production planning", "utilisation"),
         "Operational and workforce planning", "Workforce capacity and resource utilisation planning",
         "Align workforce capacity and resource allocation with operational demand."),
        (("succession", "critical role", "leadership pipeline"),
         "Talent and succession planning", "Succession and critical-role planning",
         "Plan succession coverage and future capability needs for critical roles."),
    ]
    for terms, capability, feature, description in mappings:
        if any(term in text for term in terms):
            return {
                "market_need": capability, "capability": capability,
                "feature": f"{feature}: {description}",
                "business_value": "Improve planning visibility and support better workforce and cost decisions.",
            }
    return None


def _weekly_status(metadata: dict, current_week: str) -> str:
    first_week = metadata.get("first_seen_week")
    last_week = metadata.get("last_seen_week")
    if not first_week and metadata.get("first_seen"):
        first_week = week_start(metadata["first_seen"])
    if not last_week and metadata.get("last_seen"):
        last_week = week_start(metadata["last_seen"])
    if first_week == current_week:
        return "New this week"
    if last_week == current_week:
        return "Recurring this week"
    return "Not observed this week"


def build_sheet_payloads(findings, sources, research_date=None, history_records=None):
    """Build cumulative tabs and retain weekly metadata for each historical finding."""
    today = research_date or date.today().isoformat()
    current_week = week_start(today)
    history_records = list(history_records or [])
    all_raw = list(findings or []) + history_records
    metadata_by_identity = {_identity(row) + "|" + str(row.get("source_url") or ""): row
                            for row in history_records}
    for row in findings or []:
        key = _identity(row) + "|" + str(row.get("source_url") or "")
        if key not in metadata_by_identity:
            metadata_by_identity[key] = {
                **row, "first_seen": today, "last_seen": today,
                "first_seen_week": current_week, "last_seen_week": current_week,
                "weeks_seen": [current_week], "occurrences": 1,
            }
    normalized = deduplicate_findings(all_raw)
    sources = list(sources or [])
    known_urls = {s.get("Source URL") for s in sources}
    for old in history_records:
        url = old.get("source_url")
        if url and url not in known_urls:
            sources.append({
                "Source title": old.get("source_name") or "Previously collected source",
                "Source URL": url, "Source platform": old.get("source_platform") or "Web",
                "Industry searched": old.get("industry"), "Publication date": "",
                "Collection status": "Previously collected", "Relevance status": "Historical finding",
                "Verification status": "Not verified",
                "Review notes": "Retained from append-only research history",
            })
            known_urls.add(url)

    source_id_by_url = {}
    source_rows = []
    for source in sources:
        url = source.get("Source URL") or ""
        source_id = _stable_id("SRC", url or str(source.get("Source title") or ""))
        source_id_by_url[url] = source_id
        source_rows.append([
            source_id, _cell(source.get("Source title")), _cell(url),
            _cell(source.get("Source platform") or "Website"), "",
            _cell(source.get("Industry searched")), _cell(source.get("Publication date")),
            today, "Pending review",
            "; ".join(str(f.get("description") or "") for f in normalized if f.get("source_url") == url),
            "", _cell(source.get("Collection status")), _cell(source.get("Relevance status")),
            _cell(source.get("Verification status")), _cell(source.get("Review notes")),
        ])

    finding_ids = {}
    research_rows = []
    opportunity_rows = []
    industry_groups = {}
    for row in normalized:
        meta = metadata_by_identity.get(_identity(row) + "|" + str(row.get("source_url") or ""), {})
        rid = _stable_id("RES", _identity(row) + "|" + str(row.get("source_url") or ""))
        finding_ids.setdefault(row.get("source_url"), []).append(rid)
        sid = source_id_by_url.get(row.get("source_url"), "")
        research_rows.append([
            rid, sid, _cell(row.get("industry")), _cell(row.get("sub_industry")),
            _cell(row.get("problem_type") or "Workforce planning"), _cell(row.get("problem_type")),
            _cell(row.get("description")), "", "", _cell(meta.get("last_seen") or today),
            _cell(row.get("review_status") or "Needs source verification"),
            _cell(row.get("country")), _cell(row.get("region")), _cell(row.get("source_url")),
            _cell(meta.get("first_seen")), _cell(meta.get("last_seen")),
            _cell(meta.get("weeks_seen") or [meta.get("first_seen_week"), meta.get("last_seen_week")]),
            _weekly_status(meta, current_week),
        ])
        problem = " ".join(str(row.get("problem_type") or "Unclassified").casefold().split())
        display_problem = row.get("problem_type") or "Unclassified"
        key = (row.get("industry") or "Unclassified", problem)
        group = industry_groups.setdefault(key, {
            "problem": display_problem, "ids": [], "urls": set(), "countries": set()
        })
        group["ids"].append(rid)
        if row.get("source_url"):
            group["urls"].add(row["source_url"])
        if row.get("country"):
            group["countries"].add(row["country"])
        mapped = _opportunity(row)
        if mapped:
            oid = _stable_id("OPP", rid + "|" + mapped["feature"])
            opportunity_rows.append([
                oid, _cell(row.get("industry")), _cell(row.get("problem_type")),
                mapped["market_need"], mapped["capability"], mapped["feature"],
                mapped["business_value"], "Medium", rid, _cell(row.get("source_url")),
                "Suggested - human review required",
            ])

    for source in source_rows:
        source[10] = ", ".join(finding_ids.get(source[2], []))

    insight_rows = []
    for (industry, problem), group in sorted(industry_groups.items()):
        insight_rows.append([
            _stable_id("INS", industry + "|" + problem), "Consolidated Workforce Challenges",
            industry, group["problem"], 1, len(group["urls"]), ", ".join(group["ids"]),
            ", ".join(sorted(group["countries"])), today, "AI-derived; human review required",
        ])

    problem_groups = {}
    for (industry, problem_key), group in industry_groups.items():
        problem_groups.setdefault(problem_key, []).append((industry, group))
    for problem_key, groups in problem_groups.items():
        distinct_industries = {industry for industry, _ in groups}
        if len(distinct_industries) >= 2:
            ids = [rid for _, group in groups for rid in group["ids"]]
            urls = set().union(*(group["urls"] for _, group in groups))
            countries = set().union(*(group["countries"] for _, group in groups))
            insight_rows.append([
                _stable_id("INS", "recurring|" + problem_key), "Cross-industry Workforce Challenges",
                "Multiple industries", groups[0][1]["problem"], len(distinct_industries),
                len(urls), ", ".join(ids), ", ".join(sorted(countries)), today,
                "Repeated in collected research; not prevalence proof",
            ])

    opportunity_rows = list({row[0]: row for row in opportunity_rows}.values())
    return {
        "Source Register": [SHEET_HEADERS["Source Register"]] + source_rows,
        "Market Research": [SHEET_HEADERS["Market Research"]] + research_rows,
        "Market Insights & Trends": [SHEET_HEADERS["Market Insights & Trends"]] + insight_rows,
        "Product Feature Opportunities": [SHEET_HEADERS["Product Feature Opportunities"]] + opportunity_rows,
    }


def publish_to_google_sheets(findings, sources, spreadsheet_id=None, service_account_json=None,
                             new_findings=None, recurring_findings=None, history_records=None):
    """Publish the cumulative research history to the persistent Google spreadsheet."""
    spreadsheet_id = spreadsheet_id or os.getenv("GOOGLE_SHEET_ID")
    service_account_json = service_account_json or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not spreadsheet_id or not service_account_json:
        raise RuntimeError("Set GOOGLE_SHEET_ID and GOOGLE_SERVICE_ACCOUNT_JSON to publish Google Sheets.")
    client = gspread.service_account_from_dict(json.loads(service_account_json))
    spreadsheet = client.open_by_key(spreadsheet_id)
    payloads = build_sheet_payloads(findings, sources, history_records=history_records)
    for title, values in payloads.items():
        try:
            worksheet = spreadsheet.worksheet(title)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(
                title=title, rows=max(len(values), 100), cols=max(len(values[0]), 18)
            )
        worksheet.clear()
        worksheet.resize(rows=max(len(values), 1), cols=max(len(values[0]), 1))
        worksheet.update(range_name="A1", values=values)
        worksheet.freeze(rows=1)
    return spreadsheet.url
