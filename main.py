"""CLI entry point for a global workforce intelligence run."""
import argparse
import os
from workforce_intelligence.pipeline import run_research


def main():
    parser = argparse.ArgumentParser(description="Identify public-source workforce problems globally.")
    parser.add_argument("--mode", choices=["manufacturing", "other_industries", "all_industries"], default="manufacturing")
    parser.add_argument("--country-searched", default=None, help="Optional search filter; not assumed to be the finding's actual geography.")
    parser.add_argument("--max-sources-per-industry", type=int, default=3)
    parser.add_argument("--output-dir", default="research_output")
    parser.add_argument("--history-path", default=None, help="Optional persistent JSONL history path.")
    parser.add_argument("--source-history-path", default=None, help="Persistent cumulative source register JSONL path.")
    parser.add_argument("--publish-google-sheets", action="store_true", help="Update the configured persistent Google Sheet.")
    args = parser.parse_args()
    result = run_research(
        mode=args.mode, country_searched=args.country_searched,
        max_sources_per_industry=args.max_sources_per_industry,
        output_dir=args.output_dir, history_path=args.history_path,
        publish_google_sheets=args.publish_google_sheets,
        google_sheet_id=os.getenv("GOOGLE_SHEET_ID"),
        google_service_account_json=os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"), source_history_path=args.source_history_path,
    )
    print(f"Mode: {result['mode']}")
    print(f"Sources discovered: {result['sources_discovered']}")
    print(f"Findings extracted (source-excerpt checked, not editorially reviewed): {result['findings_extracted']}")
    assessment = result.get("source_assessment_counts", {})
    print(
        "Source assessments: "
        f"{assessment.get('with_findings', 0)} with findings; "
        f"{assessment.get('no_findings', 0)} no qualifying finding; "
        f"{assessment.get('unable_to_assess', 0)} unable to assess."
    )
    if result["sources_discovered"] and not result["findings_extracted"]:
        print("WARNING: Zero findings were extracted. Review the source-assessment counts and warnings before treating this run as complete.")
    print(f"New findings: {result['new_findings']}")
    print(f"Recurring findings: {result['recurring_findings']}")
    print(f"History records: {result['history_records']}")
    if result["google_sheet_url"]:
        print(f"Google Sheet updated: {result['google_sheet_url']}")
    print(f"History: {result['history_path']}")


if __name__ == "__main__":
    main()
