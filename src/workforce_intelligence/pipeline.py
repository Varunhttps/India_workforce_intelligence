"""End-to-end orchestration for one research run."""
from pathlib import Path
import json
from .research_modes import build_research_plan
from .discovery import discover_sources
from .collector import collect_document
from .gemini_client import GeminiExtractor
from .history import update_history
from .source_history import update_source_history
from .trend_analysis import analyze_weekly_trends, analyze_opportunity_changes
from .reporting import export_workbook
from .google_sheets import _opportunity, publish_to_google_sheets


def _source_credibility_assessment(source_class, platform):
    source_class = str(source_class or "").casefold()
    platform = str(platform or "").casefold()
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


def run_research(mode="manufacturing", country_searched=None, max_sources_per_industry=5,
                 output_dir="research_output", tavily_api_key=None, gemini_api_key=None,
                 extractor=None, session=None, history_path=None,
                 publish_google_sheets=False, google_sheet_id=None,
                 google_service_account_json=None, source_history_path=None):
    plan = build_research_plan(mode)
    sources = discover_sources(plan.industries, api_key=tavily_api_key, country=country_searched,
                               max_results=max_sources_per_industry, session=session)
    raw_dir = Path(output_dir) / "raw_documents"
    findings, source_rows = [], []
    model = extractor
    if sources and model is None:
        model = GeminiExtractor(api_key=gemini_api_key)

    for source in sources:
        source_row = {
            "Source title": source.get("title"), "Source URL": source.get("url"), "Source platform": source.get("source_platform", "Web"),
            "Candidate source class (domain heuristic)": source.get("source_class", "Other / unclassified"),
            "Industry searched": source.get("industry"), "Country searched": source.get("country_searched"),
            "Actual geographic scope": None, "Region": None, "Publication date": None,
            "Search result date": source.get("search_published_date"),
            "Relevance status": "Pending automated assessment",
            "Source Credibility Assessment": _source_credibility_assessment(
                source.get("source_class"), source.get("source_platform", "Web")
            ),
        }
        try:
            collected = collect_document(source["url"], raw_dir, session=session)
            document_text = Path(collected["local_path"]).read_text(encoding="utf-8")
            rows = model.extract(document_text, source)
            for row in rows:
                row["source_url"] = source.get("url")
                row["source_name"] = source.get("title")
                row["source_platform"] = source.get("source_platform", "Web")
                if row["source_platform"] == "LinkedIn" and not row["source_url"]:
                    raise ValueError("LinkedIn finding rejected: original source URL is missing")
                findings.append(row)
            source_row["Relevance status"] = "Relevant — workforce findings extracted" if rows else "Not relevant — no qualifying workforce finding extracted"
            dates = {row.get("publication_date") for row in rows if row.get("publication_date")}
            countries = {row.get("country") for row in rows if row.get("country")}
            regions = {row.get("region") for row in rows if row.get("region")}
            if len(dates) == 1:
                source_row["Publication date"] = next(iter(dates))
            if len(countries) == 1:
                source_row["Actual geographic scope"] = next(iter(countries))
            if len(regions) == 1:
                source_row["Region"] = next(iter(regions))
        except Exception as exc:
            source_row["Relevance status"] = "Unable to assess — extraction failed"
        source_rows.append(source_row)

    history_file = history_path or str(Path(output_dir) / "findings_history.jsonl")
    history = update_history(findings, history_file)
    cumulative_history = []
    history_file_path = Path(history_file)
    if history_file_path.exists():
        for line in history_file_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    cumulative_history.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    source_history_file = source_history_path or "data/source_history.jsonl"
    source_history_records = update_source_history(source_rows, source_history_file, historical_findings=cumulative_history)
    weekly_trends = analyze_weekly_trends(cumulative_history, current_week=history["week_start"])
    opportunity_changes = analyze_opportunity_changes(
        cumulative_history, current_week=history["week_start"], classifier=_opportunity
    )
    output = Path(output_dir) / "Global_Workforce_Intelligence_Report.xlsx"
    export_workbook(findings, source_rows, output, history["new"], history["recurring"], weekly_trends, opportunity_changes)

    google_sheet_url = None
    if publish_google_sheets:
        historical_records = []
        history_path_obj = Path(history_file)
        if history_path_obj.exists():
            for line in history_path_obj.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        historical_records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        google_sheet_url = publish_to_google_sheets(
            findings, source_rows, spreadsheet_id=google_sheet_id,
            service_account_json=google_service_account_json,
            new_findings=history["new"], recurring_findings=history["recurring"],
            history_records=historical_records,
        )

    return {
        "mode": plan.mode, "industries": list(plan.industries),
        "sources_discovered": len(sources), "findings_extracted": len(findings),
        "new_findings": len(history["new"]), "recurring_findings": len(history["recurring"]),
        "history_records": history["history_records"], "history_path": history["history_path"],
        "weekly_trends": weekly_trends, "opportunity_changes": opportunity_changes,
        "workbook_path": str(output), "google_sheet_url": google_sheet_url,
        "findings": findings, "sources": source_rows,
    }
