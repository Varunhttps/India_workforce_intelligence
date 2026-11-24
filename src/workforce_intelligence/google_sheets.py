"""Publish cumulative and week-aware workforce intelligence to Google Sheets."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from typing import Any

import gspread

from .history import week_start
from .trend_analysis import analyze_weekly_trends
from .records import deduplicate_findings
from .source_history import save_source_history

SHEET_HEADERS = {
    "Source Register": [
        "Source ID", "Source Title", "Source URL", "Source Type",
        "Publisher / Author", "Industry", "Publication Date", "Access Date",
        "Related Research IDs",
    ],
    "Market Research": [
        "Research ID", "Source ID", "Industry", "Sub-industry",
        "Workforce Planning Area", "Identified Problem", "Problem Description",
        "Research Date", "Country", "Region", "Source URL",
        "First Seen", "Latest Week", "Observation Weeks",
    ],
    "Market Insights & Trends": [
        "Insight ID", "Section", "Industry", "Insight / Challenge",
        "Distinct Problem Count", "Supporting Source Count", "Related Research IDs",
        "Countries", "Latest Evidence Date",
    ],
    "Product Feature Opportunities": [
        "Opportunity ID", "Industry", "Identified Market Problem", "Market Need",
        "Proposed Product Capability", "Suggested Feature & Description",
        "Expected Business Value", "Priority", "Related Research IDs",
        "Supporting Source URLs", "Last Updated",
    ],
    "Weekly Trends": [
        "Trend ID", "Industry", "Workforce Problem", "Supporting Sources", "Weeks Seen", "Latest Evidence Date",
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


def _observation_weeks(metadata: dict) -> str:
    """Return exact distinct ISO observation weeks for dashboard signal calculations."""
    values = metadata.get("weeks_seen") or []
    if isinstance(values, str):
        values = [part.strip() for part in values.split(",") if part.strip()]
    if not values:
        values = [
            metadata.get("first_seen_week"), metadata.get("last_seen_week"),
            metadata.get("first_seen"), metadata.get("last_seen"),
        ]
    normalized = set()
    for value in values:
        if not value:
            continue
        try:
            normalized.add(week_start(value))
        except (TypeError, ValueError):
            continue
    return ", ".join(sorted(normalized))


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
    """Map workforce problems to specific, buildable industry product concepts."""
    problem = str(row.get("problem_type") or "").casefold()
    description = str(row.get("description") or "").casefold()
    text = f"{problem} {description}"
    industry = str(row.get("industry") or "").casefold()

    high_terms = ("critical", "severe", "urgent", "crisis", "plant shutdown",
                  "production halted", "missed orders", "major disruption",
                  "safety risk", "high turnover", "large-scale", "mass",
                  "persistent", "significant shortage", "unfilled for months",
                  "production disruption")
    if any(term in text for term in high_terms) or supporting_source_count >= 3:
        priority = "High"
    elif supporting_source_count >= 2:
        priority = "Medium"
    else:
        priority = "Low"

    industry_outcomes = {
        "manufactur": "line uptime, throughput, quality, scrap and shift coverage",
        "health": "patient coverage, credential compliance, safe staffing and care continuity",
        "hospital": "patient coverage, credential compliance, safe staffing and care continuity",
        "logistic": "warehouse throughput, delivery reliability and peak-demand coverage",
        "construct": "project milestones, crew availability and site safety",
        "agricultur": "seasonal crew availability, harvest windows and field productivity",
        "energy": "asset uptime, outage response, field crew readiness and safety",
        "retail": "store coverage, peak-hour service and customer experience",
        "information technology": "delivery capacity, critical skills and project execution",
        "financial": "service coverage, operational resilience and cost control",
    }
    outcome = next((v for key, v in industry_outcomes.items() if key in industry),
                  "operational capacity, service levels, workforce continuity and cost")

    rules = [
        (("payroll", "compensation", "benefit cost", "salary", "wage", "labour cost", "labor cost"),
         "Compensation and payroll cost pressure", "Workforce cost planning module",
         "Compensation Scenario Simulator",
         "Compare wage bands, benefits, overtime, shift premiums and headcount by site and role; show budget variance and cost per output.",
         "Improve labour-cost visibility and support budget decisions."),
        (("succession", "retirement risk", "critical role", "leadership pipeline"),
         "Critical-role continuity and succession risk", "Critical-role continuity platform",
         "Critical Role Coverage Map",
         "Show retirement exposure, single-incumbent roles, successor readiness, time-to-proficiency and coverage gaps; create succession action plans.",
         "Reduce single-person dependency and protect business-critical roles."),
        (("skill gap", "skills gap", "skills mismatch", "skill mismatch", "reskilling", "upskilling", "skills shortage"),
         "Workforce skills and capability gap", "Skills intelligence and development platform",
         "Skills-to-Work Demand Mapper",
         "Compare employee skills with target-role requirements, rank gaps, map cross-training opportunities and generate learning pathways.",
         "Direct training spend to measurable gaps and improve redeployment."),
        (("attrition", "turnover", "retention", "employee disengagement", "employee engagement"),
         "Employee retention and attrition pressure", "Retention analytics and intervention service",
         "Attrition Risk & Root-Cause Dashboard",
         "Track attrition by role, site, tenure and cohort; connect trends to exit reasons and engagement data and track retention interventions.",
         "Identify retention hotspots earlier and focus on costly replacement risks."),
        (("absenteeism", "absence", "burnout", "overtime", "fatigue", "workload"),
         "Workload, absence and workforce availability pressure", "Workforce availability planning tool",
         "Shift Coverage & Fatigue Planner",
         "Forecast shift staffing from absence, overtime, qualifications and workload; flag uncovered shifts and fatigue conflicts and suggest coverage options.",
         "Reduce coverage gaps and excessive overtime."),
        (("allocation", "understaff", "overstaff", "staffing level", "workforce distribution", "deployment"),
         "Workforce allocation imbalance", "Demand-led staffing optimisation",
         "Site and Team Staffing Optimiser",
         "Compare demand forecasts with headcount by location, skill and shift; recommend transfers, schedule changes or targeted hiring.",
         "Align staffing with workload and improve utilisation."),
        (("productivity", "inefficiency", "low output", "low efficiency", "utilisation"),
         "Workforce productivity and utilisation challenge", "Operational productivity analytics",
         "Labour Productivity Variance Monitor",
         "Combine labour hours, output, quality and rework by team and site; show productivity variance and compare improvement interventions.",
         "Expose productivity losses and support process improvement."),
        (("production capacity", "capacity constraint", "production bottleneck", "manufacturing capacity"),
         "Production capacity and operational bottleneck", "Production and workforce capacity planning",
         "Line Capacity & Skill Coverage Simulator",
         "Model output against staffing, skill mix, downtime and demand; identify bottleneck roles and test shift and training plans.",
         "Improve production readiness and reduce workforce-driven throughput constraints."),
        (("shortage", "vacancy", "recruit", "hiring", "hard to fill", "unfilled position", "talent acquisition"),
         "Hiring demand and hard-to-fill roles", "Targeted hiring intelligence product",
         "Hard-to-Fill Role Demand Forecast",
         "Forecast vacancies by role, location and skill using demand, attrition and time-to-fill; prioritise critical roles and recruiter workload.",
         "Focus recruitment resources on roles most likely to disrupt operations."),
    ]
    for terms, need, capability, feature, feature_detail, value in rules:
        if any(term in text for term in terms):
            industry_detail = {
                "manufactur": "Include machine/line skill matrices, operator certifications, cross-training and shift-level coverage.",
                "health": "Include unit-level staffing demand, credentials, competency coverage and safe-staffing constraints.",
                "logistic": "Include warehouse zones, routes, throughput targets, shift demand and peak periods.",
                "construct": "Include site, trade, crew availability, project milestones and required safety qualifications.",
                "agricultur": "Include crop, field, task, seasonal crew demand and harvest-window forecasts.",
                "energy": "Include asset/site, outage schedules, field crew qualifications and safety coverage.",
                "retail": "Include store, role, peak-hour demand and service coverage.",
            }
            detail = next((v for k, v in industry_detail.items() if k in industry),
                         f"Configure metrics and scenarios around {outcome}.")
            return {
                "market_need": need,
                "capability": capability,
                "feature": f"{feature}: {feature_detail} Industry implementation: {detail}",
                "business_value": f"{value} Expected industry outcome: improve {outcome}.",
                "priority": priority,
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
            today, "",
        ])

    finding_ids = {}
    research_rows = []
    opportunity_rows = []
    industry_groups = {}
    problem_source_counts = {}
    for item in normalized:
        pkey = (item.get("industry") or "Unclassified", " ".join(str(item.get("problem_type") or "Unclassified").casefold().split()))
        problem_source_counts.setdefault(pkey, set()).add(item.get("source_url") or "")
    for row in normalized:
        meta = metadata_by_identity.get(_identity(row) + "|" + str(row.get("source_url") or ""), {})
        rid = _stable_id("RES", _identity(row) + "|" + str(row.get("source_url") or ""))
        finding_ids.setdefault(row.get("source_url"), []).append(rid)
        sid = source_id_by_url.get(row.get("source_url"), "")
        research_rows.append([
            rid, sid, _cell(row.get("industry")), _cell(row.get("sub_industry")),
            _cell(row.get("problem_type") or "Workforce planning"), _cell(row.get("problem_type")),
            _cell(row.get("description")), _cell(meta.get("last_seen") or today),
            _cell(row.get("country")), _cell(row.get("region")), _cell(row.get("source_url")),
            _cell(meta.get("first_seen")),
            _cell(meta.get("last_seen_week") or week_start(meta.get("last_seen") or today)),
            _observation_weeks(meta),
        ])
        problem = " ".join(str(row.get("problem_type") or "Unclassified").casefold().split())
        display_problem = row.get("problem_type") or "Unclassified"
        key = (row.get("industry") or "Unclassified", problem)
        group = industry_groups.setdefault(key, {
            "problem": display_problem, "ids": [], "urls": set(), "countries": set(), "latest_evidence_date": ""
        })
        group["ids"].append(rid)
        evidence_date = str(meta.get("last_seen") or today)
        group["latest_evidence_date"] = max(group["latest_evidence_date"], evidence_date)
        if row.get("source_url"):
            group["urls"].add(row["source_url"])
        if row.get("country"):
            group["countries"].add(row["country"])
        mapped = _opportunity(row, supporting_source_count=len(problem_source_counts.get(key, set())))
        if mapped:
            oid = _stable_id("OPP", rid + "|" + mapped["feature"])
            opportunity_rows.append([
                oid, _cell(row.get("industry")), _cell(row.get("problem_type")),
                mapped["market_need"], mapped["capability"], mapped["feature"],
                mapped["business_value"], mapped["priority"], rid, _cell(row.get("source_url")),
                _cell(meta.get("last_seen") or today),
            ])

    for source in source_rows:
        source[8] = ", ".join(finding_ids.get(source[2], []))

    # Manager-facing summary: one row per industry, with detailed records retained in Market Research.
    industry_summaries = {}
    for (industry, problem_key), group in industry_groups.items():
        summary = industry_summaries.setdefault(industry, {
            "problem_keys": set(), "problem_labels": [], "ids": [],
            "urls": set(), "countries": set(), "latest_evidence_date": "",
        })
        summary["problem_keys"].add(problem_key)
        summary["problem_labels"].append(group["problem"])
        summary["ids"].extend(group["ids"])
        summary["urls"].update(group["urls"])
        summary["countries"].update(group["countries"])
        summary["latest_evidence_date"] = max(summary["latest_evidence_date"], group["latest_evidence_date"])

    insight_rows = []
    for industry, summary in sorted(industry_summaries.items()):
        problems = sorted(set(summary["problem_labels"]), key=str.casefold)
        insight_rows.append([
            _stable_id("INS", industry), "Industry Summary", industry,
            "; ".join(problems), len(summary["problem_keys"]), len(summary["urls"]),
            ", ".join(sorted(set(summary["ids"]))),
            ", ".join(sorted(summary["countries"])), summary["latest_evidence_date"] or today,
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
    trend_rows = []
    for trend in weekly_trends:
        trend_id = _stable_id("TRD", trend["industry"] + "|" + trend["problem_type"])
        trend_rows.append([
            trend_id, trend["industry"], trend["problem_type"],
            _cell(trend["supporting_sources"]), int(trend["weeks_observed"]),
            _cell(trend.get("last_seen")),
        ])

    source_rows.sort(key=lambda row: (str(row[5] or "").casefold(), str(row[1] or "").casefold()))
    research_rows.sort(key=lambda row: (str(row[2] or "").casefold(), str(row[5] or "").casefold()))
    insight_rows.sort(key=lambda row: (str(row[2] or "").casefold()))
    opportunity_rows.sort(key=lambda row: (str(row[1] or "").casefold(), str(row[2] or "").casefold()))
    trend_rows.sort(key=lambda row: (str(row[1] or "").casefold(), str(row[2] or "").casefold()))
    return {
        "Source Register": [SHEET_HEADERS["Source Register"]] + source_rows,
        "Market Research": [SHEET_HEADERS["Market Research"]] + research_rows,
        "Market Insights & Trends": [SHEET_HEADERS["Market Insights & Trends"]] + insight_rows,
        "Product Feature Opportunities": [SHEET_HEADERS["Product Feature Opportunities"]] + opportunity_rows,
        "Weekly Trends": [SHEET_HEADERS["Weekly Trends"]] + trend_rows,
    }


def publish_to_google_sheets(findings, sources, spreadsheet_id=None, service_account_json=None,
                             new_findings=None, recurring_findings=None, history_records=None,
                             source_history_records=None, source_history_path=None):
    """Publish the cumulative research history while permanently migrating old source dates."""
    spreadsheet_id = spreadsheet_id or os.getenv("GOOGLE_SHEET_ID")
    service_account_json = service_account_json or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not spreadsheet_id or not service_account_json:
        raise RuntimeError("Set GOOGLE_SHEET_ID and GOOGLE_SERVICE_ACCOUNT_JSON to publish Google Sheets.")
    client = gspread.service_account_from_dict(json.loads(service_account_json))
    spreadsheet = client.open_by_key(spreadsheet_id)
    # Read the existing register before replacing it; preserve historical URLs and dates.
    try:
        old_register = spreadsheet.worksheet("Source Register").get_all_values()
    except gspread.WorksheetNotFound:
        old_register = []
    legacy_by_url = {}
    if old_register:
        headers = old_register[0]
        if "Source URL" in headers:
            url_col = headers.index("Source URL")
            date_col = headers.index("Access Date") if "Access Date" in headers else None
            for row in old_register[1:]:
                if len(row) <= url_col or not row[url_col]:
                    continue
                url = row[url_col]
                access_date = row[date_col] if date_col is not None and len(row) > date_col else ""
                legacy_by_url[url] = access_date
    records_by_url = {record.get("source_url") or record.get("Source URL"): dict(record)
                       for record in (source_history_records or [])
                       if record.get("source_url") or record.get("Source URL")}
    # Bootstrap from the live sheet. Existing nonblank dates remain unchanged;
    # blank legacy dates remain blank rather than being falsely dated today.
    for url, access_date in legacy_by_url.items():
        record = records_by_url.get(url, {"source_url": url})
        if access_date:
            record["first_found_date"] = access_date
        else:
            record.setdefault("first_found_date", "")
        records_by_url[url] = record
    migrated_records = list(records_by_url.values())
    if source_history_path:
        save_source_history(migrated_records, source_history_path)
    # Delete the obsolete worksheet requested for removal from the workbook.
    try:
        obsolete = spreadsheet.worksheet("Opportunity Changes")
    except gspread.WorksheetNotFound:
        obsolete = None
    if obsolete is not None:
        spreadsheet.del_worksheet(obsolete)
    payloads = build_sheet_payloads(findings, sources, history_records=history_records,
                                    source_history_records=migrated_records)
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
        if title == "Weekly Trends":
            worksheet.format("E:E", {"numberFormat": {"type": "NUMBER", "pattern": "0"}})
    return spreadsheet.url
