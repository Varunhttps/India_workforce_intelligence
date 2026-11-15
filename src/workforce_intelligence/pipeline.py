"""End-to-end orchestration for one research run."""
from pathlib import Path
from .research_modes import build_research_plan
from .discovery import discover_sources
from .collector import collect_document
from .gemini_client import GeminiExtractor
from .reporting import export_workbook

def run_research(mode="manufacturing", country_searched=None, max_sources_per_industry=5, output_dir="research_output", tavily_api_key=None, gemini_api_key=None, extractor=None, session=None):
    plan = build_research_plan(mode)
    sources = discover_sources(plan.industries, api_key=tavily_api_key, country=country_searched, max_results=max_sources_per_industry, session=session)
    raw_dir = Path(output_dir) / "raw_documents"
    findings, source_rows = [], []
    # No Gemini key is needed if discovery returns no candidates.
    model = extractor
    if sources and model is None:
        model = GeminiExtractor(api_key=gemini_api_key)

    for source in sources:
        source_row = {
            "Source title": source.get("title"), "Source URL": source.get("url"),
            "Industry searched": source.get("industry"), "Country searched": source.get("country_searched"),
            "Actual geographic scope": None, "Region": None,
            # A search engine's date is not the report's verified publication date.
            "Publication date": None, "Search result date": source.get("search_published_date"),
            "Collection status": "Not collected", "Relevance status": "Candidate - review required",
            "Verification status": "Not verified", "Review notes": None,
        }
        try:
            collected = collect_document(source["url"], raw_dir, session=session)
            source_row["Collection status"] = "Collected"
            document_text = Path(collected["local_path"]).read_text(encoding="utf-8")
            rows = model.extract(document_text, source)
            for row in rows:
                row["industry"] = row.get("industry") or source.get("industry")
                row["review_status"] = "Needs source verification"
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
        except Exception as exc:
            source_row["Collection status"] = "Failed"
            source_row["Review notes"] = f"{type(exc).__name__}: {exc}"[:500]
        source_rows.append(source_row)

    output = Path(output_dir) / "Global_Workforce_Intelligence_Report.xlsx"
    export_workbook(findings, source_rows, output)
    return {"mode": plan.mode, "industries": list(plan.industries), "sources_discovered": len(sources), "findings_extracted": len(findings), "workbook_path": str(output), "findings": findings, "sources": source_rows}
