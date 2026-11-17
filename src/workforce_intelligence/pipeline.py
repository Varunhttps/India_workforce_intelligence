"""End-to-end orchestration for one research run."""
from pathlib import Path
import json
from .research_modes import build_research_plan
from .discovery import discover_sources
from .collector import collect_document
from .gemini_client import GeminiExtractor
from .history import update_history
from .reporting import export_workbook
from .google_sheets import publish_to_google_sheets


def run_research(mode="manufacturing", country_searched=None, max_sources_per_industry=5,
                 output_dir="research_output", tavily_api_key=None, gemini_api_key=None,
                 extractor=None, session=None, history_path=None,
                 publish_google_sheets=False, google_sheet_id=None,
                 google_service_account_json=None):
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
            "Search result date": source.get("search_published_date"), "Collection status": "Not collected",
            "Relevance status": "Candidate - review required", "Verification status": "Not verified",
            "Review notes": None,
        }
        try:
            collected = collect_document(source["url"], raw_dir, session=session)
            source_row["Collection status"] = "Collected"
            document_text = Path(collected["local_path"]).read_text(encoding="utf-8")
            rows = model.extract(document_text, source)
            for row in rows:
                row["source_url"] = source.get("url")
                row["source_name"] = source.get("title")
                row["source_platform"] = source.get("source_platform", "Web")
                if row["source_platform"] == "LinkedIn" and not row["source_url"]:
                    raise ValueError("LinkedIn finding rejected: original source URL is missing")
                row["review_status"] = row.get("review_status") or "Needs source verification"
                findings.append(row)
            source_row["Relevance status"] = "Findings extracted" if rows else "No qualifying finding extracted"
            dates = {row.get("publication_date") for row in rows if row.get("publication_date")}
            countries = {row.get("country") for row in rows if row.get("country")}
            regions = {row.get("region") for row in rows if row.get("region")}
            if len(dates) == 1:
                source_row["Publication date"] = next(iter(dates))
            if len(countries) == 1:
                source_row["Actual geographic scope"] = next(iter(countries))
            if len(regions) == 1:
                source_row["Region"] = next(iter(regions))
            if rows and all(row.get("review_status") == "Quote matched; human review required" for row in rows):
                source_row["Verification status"] = "Exact quote match passed; interpretation needs review"
        except Exception as exc:
            if source_row["Collection status"] == "Not collected":
                source_row["Collection status"] = "Failed"
            else:
                source_row["Relevance status"] = "Extraction failed"
            source_row["Review notes"] = f"{type(exc).__name__}: {exc}"[:500]
        source_rows.append(source_row)

    history_file = history_path or str(Path(output_dir) / "findings_history.jsonl")
    history = update_history(findings, history_file)
    output = Path(output_dir) / "Global_Workforce_Intelligence_Report.xlsx"
    export_workbook(findings, source_rows, output, history["new"], history["recurring"])

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
        "workbook_path": str(output), "google_sheet_url": google_sheet_url,
        "findings": findings, "sources": source_rows,
    }
