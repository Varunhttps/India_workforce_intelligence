"""CLI entry point for a global workforce intelligence run."""
import argparse
from workforce_intelligence.pipeline import run_research

def main():
    parser=argparse.ArgumentParser(description="Identify public-source workforce problems globally.")
    parser.add_argument("--mode",choices=["manufacturing","other_industries","all_industries"],default="manufacturing")
    parser.add_argument("--country-searched",default=None,help="Optional search filter; not assumed to be the finding's actual geography.")
    parser.add_argument("--max-sources-per-industry",type=int,default=3)
    parser.add_argument("--output-dir",default="research_output")
    args=parser.parse_args()
    result=run_research(mode=args.mode,country_searched=args.country_searched,max_sources_per_industry=args.max_sources_per_industry,output_dir=args.output_dir)
    print(f"Mode: {result['mode']}")
    print(f"Sources discovered: {result['sources_discovered']}")
    print(f"Findings extracted (not yet verified): {result['findings_extracted']}")
    print(f"Workbook: {result['workbook_path']}")
if __name__=="__main__": main()
