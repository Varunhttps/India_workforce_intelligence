"""Publish cumulative and week-aware workforce intelligence to Google Sheets."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from typing import Any

import gspread

from .history import week_start
from .trend_analysis import analyze_weekly_trends, analyze_opportunity_changes
from .records import deduplicate_findings

SHEET_HEADERS = {
    "Source Register": [
        "Source ID", "Source Title", "Source URL", "Source Type",
        "Publisher / Author", "Industry", "Publication Date", "Access Date",
        "Source Credibility Assessment", "Related Research IDs",
        "Relevance Status",
    ],
    "Market Research": [
        "Research ID", "Source ID", "Industry", "Sub-industry",
        "Workforce Planning Area", "Identified Problem", "Problem Description",
        "Business Impact", "Publication Date", "Research Date",
        "Country", "Region", "Source URL",
        "First Seen", "Last Seen", "Weeks Seen", "Occurrences", "Weekly Status",
    ],
    "Market Insights & Trends": [
        "Insight ID", "Section", "Industry", "Insight / Challenge",
        "Distinct Problem Count", "Supporting Source Count", "Related Research IDs",
        "Countries", "Research Date",
    ],
    "Weekly Trends": [
        "Trend ID", "Industry", "Workforce Problem", "Signal Status", "Signal Momentum",
        "Emerging Signal", "Potentially Worsening", "Weeks Observed", "Total Countries",
        "Countries This Week", "Countries Previous Week", "Country Count Delta",
        "Total Sources", "Sources This Week", "Sources Previous Week", "Source Count Delta",
        "Supporting Sources", "First Seen", "Last Seen", "Latest Week", "Current Week",
    ],
    "Opportunity Changes": [
        "Opportunity ID", "Industry", "Market Need", "Capability", "Suggested Feature",
        "Business Value", "Priority", "Change Status", "New This Week", "Expanded Evidence",
        "Weeks Observed", "Total Countries", "Countries This Week", "Countries Previous Week",
        "Country Count Delta", "Total Sources", "Sources This Week", "Sources Previous Week",
        "Source Count Delta", "Supporting Sources", "First Seen", "Last Seen", "Latest Week",
        "Current Week",
    ],
    "Product Feature Opportunities": [
        "Opportunity ID", "Industry", "Identified Market Problem", "Market Need",
        "Proposed Product Capability", "Suggested Feature & Description",
        "Expected Business Value", "Priority", "Related Research IDs",
        "Supporting Source URLs",
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


def _source_credibility(source: dict) -> str:
    """Rule-based publisher/source assessment; not a guarantee of article accuracy."""
    source_class = str(source.get("Candidate source class (domain heuristic)") or "").casefold()
    platform = str(source.get("Source platform") or "").casefold()
    if platform == "linkedin":
        return "Limited — user-generated content; treated as a supporting signal only"
    if "government" in source_class or "intergovernmental" in source_class:
        return "High — official or multilateral publisher"
    if "academic" in source_class:
        return "High — academic domain"
    if "research / consulting" in source_class:
        return "Moderate to high — established research/consulting publisher"
    if "industry body" in source_class:
        return "Moderate — industry association or trade body"
    return "Unclassified — publisher type not recognised by current rules"


def _identity(row: dict) -> str:
    return "|".join(str(row.get(k) or "").strip().casefold()
                    for k in ("industry", "problem_type", "description", "country"))


def _opportunity(row: dict, supporting_source_count: int = 1) -> dict | None:
    """Map distinct workforce problem types to distinct planning capabilities."""
    problem = str(row.get("problem_type") or "").casefold()
    description = str(row.get("description") or "").casefold()
    text = f"{problem} {description}"
    severity_terms = ("critical", "severe", "urgent", "crisis", "plant shutdown",
                      "production halted", "missed orders", "major disruption")
    high_terms = ("high turnover", "large-scale", "mass", "persistent", "significant shortage",
                  "unfilled for months", "production disruption", "safety risk")
    if any(term in text for term in severity_terms + high_terms) or supporting_source_count >= 4:
        priority = "High"
    elif supporting_source_count >= 2:
        priority = "Medium"
    else:
        priority = "Low"
    rules = [
        (("payroll", "compensation", "benefit cost", "salary", "wage", "labour cost", "labor cost"),
         "Compensation and payroll cost pressure", "Compensation and financial planning",
         "Compensation, benefits and payroll forecasting",
         "Model pay, benefits and payroll scenarios alongside workforce plans.",
         "Improve labour-cost visibility and support affordability decisions."),
        (("succession", "retirement risk", "critical role", "leadership pipeline"),
         "Critical-role continuity and succession risk", "Succession and critical-role planning",
         "Succession coverage and capability pipeline",
         "Identify critical roles, successor coverage and future capability gaps.",
         "Reduce continuity risk in business-critical roles."),
        (("skill gap", "skills gap", "skills mismatch", "skill mismatch", "reskilling", "upskilling", "skills shortage"),
         "Workforce skills and capability gap", "Skills and capability planning",
         "Skills inventory and capability-gap scenarios",
         "Compare required skills with available workforce capabilities and model reskilling needs.",
         "Target capability investment and reduce persistent skills mismatches."),
        (("attrition", "turnover", "retention", "employee disengagement", "employee engagement"),
         "Employee retention and attrition pressure", "Retention and workforce scenario planning",
         "Attrition forecasting and retention scenario planning",
         "Model attrition assumptions by role, location and team and assess replacement demand.",
         "Anticipate replacement needs and improve workforce continuity."),
        (("absenteeism", "absence", "burnout", "overtime", "fatigue", "workload"),
         "Workload, absence and workforce availability pressure", "Workforce capacity and availability planning",
         "Absence, overtime and workload capacity modelling",
         "Model available capacity after absence and overtime assumptions across teams and sites.",
         "Improve capacity planning and reduce unplanned workload pressure."),
        (("allocation", "understaff", "overstaff", "staffing level", "workforce distribution", "deployment"),
         "Workforce allocation imbalance", "Workforce allocation and headcount planning",
         "Headcount allocation by site, team and demand",
         "Compare planned headcount with operational demand and model reallocations across sites.",
         "Improve utilisation and align staffing with demand."),
        (("productivity", "inefficiency", "low output", "low efficiency", "utilisation"),
         "Workforce productivity and utilisation challenge", "Resource utilisation and productivity planning",
         "Productivity and resource-utilisation scenarios",
         "Compare workforce capacity, planned output and resource utilisation to expose gaps.",
         "Support more effective use of existing workforce capacity."),
        (("production capacity", "capacity constraint", "production bottleneck", "manufacturing capacity"),
         "Production capacity and operational bottleneck", "Production and workforce capacity planning",
         "Demand-linked production capacity scenarios",
         "Align workforce capacity and production plans with demand and operational constraints.",
         "Improve production readiness and resource alignment."),
        (("shortage", "vacancy", "recruit", "hiring", "hard to fill", "unfilled position", "talent acquisition"),
         "Hiring demand and hard-to-fill roles", "Talent acquisition and workforce demand planning",
         "Hiring demand, vacancy and time-to-fill forecasting",
         "Forecast hiring demand by role, skill and location and connect vacancies to workforce plans.",
         "Improve hiring visibility and anticipate staffing gaps."),
    ]
    for terms, need, capability, feature, description_text, value in rules:
        if any(term in text for term in terms):
            return {"market_need": need, "capability": capability,
                    "feature": f"{feature}: {description_text}",
                    "business_value": value, "priority": priority}
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
    return "Last seen before this week"


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
                "Relevance status": "Historical finding",
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
            today, _source_credibility(source),
            "", _cell(source.get("Relevance status")),
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
            _cell(row.get("description")), _cell(row.get("business_impact")),
            _cell(row.get("publication_date")), _cell(meta.get("last_seen") or today),
            _cell(row.get("country")), _cell(row.get("region")), _cell(row.get("source_url")),
            _cell(meta.get("first_seen")), _cell(meta.get("last_seen")),
            _cell(meta.get("weeks_seen") or [meta.get("first_seen_week"), meta.get("last_seen_week")]),
            _cell(meta.get("occurrences", 1)), _weekly_status(meta, current_week),
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
        mapped = _opportunity(row, supporting_source_count=len(group["urls"]))
        if mapped:
            oid = _stable_id("OPP", rid + "|" + mapped["feature"])
            opportunity_rows.append([
                oid, _cell(row.get("industry")), _cell(row.get("problem_type")),
                mapped["market_need"], mapped["capability"], mapped["feature"],
                mapped["business_value"], mapped["priority"], rid, _cell(row.get("source_url")),
            ])

    for source in source_rows:
        source[9] = ", ".join(finding_ids.get(source[2], []))

    # Manager-facing summary: one row per industry, with detailed records retained in Market Research.
    industry_summaries = {}
    for (industry, problem_key), group in industry_groups.items():
        summary = industry_summaries.setdefault(industry, {
            "problem_keys": set(), "problem_labels": [], "ids": [],
            "urls": set(), "countries": set(),
        })
        summary["problem_keys"].add(problem_key)
        summary["problem_labels"].append(group["problem"])
        summary["ids"].extend(group["ids"])
        summary["urls"].update(group["urls"])
        summary["countries"].update(group["countries"])

    insight_rows = []
    for industry, summary in sorted(industry_summaries.items()):
        problems = sorted(set(summary["problem_labels"]), key=str.casefold)
        insight_rows.append([
            _stable_id("INS", industry), "Industry Summary", industry,
            "; ".join(problems), len(summary["problem_keys"]), len(summary["urls"]),
            ", ".join(sorted(set(summary["ids"]))),
            ", ".join(sorted(summary["countries"])), today,
        ])

    opportunity_rows = list({row[0]: row for row in opportunity_rows}.values())
    analysis_records = list(history_records)
    seen_records = {_identity(row) + "|" + str(row.get("source_url") or "") for row in analysis_records}
    for row in normalized:
        key = _identity(row) + "|" + str(row.get("source_url") or "")
        if key in seen_records:
            continue
        meta = metadata_by_identity.get(key, {})
        analysis_records.append({
            **row,
            "first_seen": meta.get("first_seen", today),
            "last_seen": meta.get("last_seen", today),
            "first_seen_week": meta.get("first_seen_week", current_week),
            "last_seen_week": meta.get("last_seen_week", current_week),
            "weeks_seen": meta.get("weeks_seen", [current_week]),
            "occurrences": meta.get("occurrences", 1),
        })
        seen_records.add(key)

    weekly_trends = analyze_weekly_trends(analysis_records, current_week=current_week)
    opportunity_changes = analyze_opportunity_changes(
        analysis_records, current_week=current_week, classifier=_opportunity
    )
    trend_rows = []
    for trend in weekly_trends:
        trend_id = _stable_id("TRD", trend["industry"] + "|" + trend["problem_type"])
        trend_rows.append([
            trend_id, trend["industry"], trend["problem_type"], trend["signal_status"],
            trend["signal_momentum"], trend["emerging_signal"], trend["worsening_signal"],
            trend["weeks_observed"], trend["country_count"], trend["current_week_country_count"],
            trend["previous_week_country_count"], trend["country_count_delta"],
            trend["source_count"], trend["current_week_source_count"],
            trend["previous_week_source_count"], trend["source_count_delta"],
            _cell(trend["supporting_sources"]), trend["first_seen"], trend["last_seen"],
            trend["latest_week"], trend["current_week"],
        ])
    opportunity_change_rows = []
    for opportunity in opportunity_changes:
        opportunity_id = _stable_id("OCH", opportunity["industry"] + "|" + opportunity["capability"])
        opportunity_change_rows.append([
            opportunity_id, opportunity["industry"], opportunity["market_need"],
            opportunity["capability"], opportunity["feature"], opportunity["business_value"],
            opportunity["priority"], opportunity["change_status"], opportunity["new_this_week"],
            opportunity["expanded_evidence"], opportunity["weeks_observed"],
            opportunity["country_count"], opportunity["current_week_country_count"],
            opportunity["previous_week_country_count"], opportunity["country_count_delta"],
            opportunity["source_count"], opportunity["current_week_source_count"],
            opportunity["previous_week_source_count"], opportunity["source_count_delta"],
            _cell(opportunity["supporting_sources"]), opportunity["first_seen"],
            opportunity["last_seen"], opportunity["latest_week"], opportunity["current_week"],
        ])

    return {
        "Source Register": [SHEET_HEADERS["Source Register"]] + source_rows,
        "Market Research": [SHEET_HEADERS["Market Research"]] + research_rows,
        "Market Insights & Trends": [SHEET_HEADERS["Market Insights & Trends"]] + insight_rows,
        "Product Feature Opportunities": [SHEET_HEADERS["Product Feature Opportunities"]] + opportunity_rows,
        "Weekly Trends": [SHEET_HEADERS["Weekly Trends"]] + trend_rows,
        "Opportunity Changes": [SHEET_HEADERS["Opportunity Changes"]] + opportunity_change_rows,
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
