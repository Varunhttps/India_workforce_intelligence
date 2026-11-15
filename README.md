# Global Workforce Intelligence Agent

A global public-source research agent that identifies and classifies reported workforce problems. Manufacturing is the primary research focus; users can also explore other industries or run an all-industry scan. The agent identifies problems and does not generate solutions.

## Research modes
- **Manufacturing Research** (default): automotive, electronics, semiconductors, machinery, chemicals, pharmaceuticals, food and beverage, textiles, metals and aerospace manufacturing.
- **Explore Other Industries**: construction, healthcare, IT, logistics, retail, hospitality, education, energy, agriculture and financial services.
- **All Industries**: both groups.

## Pipeline
1. Discover candidate public sources using Tavily.
2. Collect accessible HTML and PDF documents.
3. Extract reported workforce problems into structured records using Gemini.
4. Export a manager-facing Excel workbook with Workforce Findings, Source Register and Research Summary sheets.

All model-extracted findings remain marked **Needs source verification**. Search-result dates are stored separately from publication dates stated in source material. Search country is not treated as proof of the actual geography of a finding.

## Setup
Python 3.10+ recommended.

```bash
pip install -r requirements.txt
export TAVILY_API_KEY="your-key"
export GEMINI_API_KEY="your-key"
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python main.py --mode manufacturing --max-sources-per-industry 3
```

Available modes: `manufacturing`, `other_industries`, `all_industries`.

## Weekly automation
The scheduled GitHub Actions workflow is configured for Mondays at 06:00 UTC (11:30 India Standard Time). It requires repository Actions secrets named `TAVILY_API_KEY` and `GEMINI_API_KEY`. A successful run publishes the Excel workbook as a downloadable workflow artifact retained for 30 days.

**Activation requirements:** GitHub Actions schedules run from the repository's default branch. Merge this workflow to the default branch and add both repository secrets under Settings → Secrets and variables → Actions. Until those steps are completed and a scheduled/manual run succeeds, weekly updates are configured but not operational.

## Workbook fields
The findings sheet contains problem type, description, country, region, industry, sub-industry, company, source name, source URL, publication date, data period and review status. Evidence, Confidence and HR Category columns are intentionally excluded. The source register records source metadata, collection status, search-result date, source publication date, and verification status.

## Current limitations
- Search results are candidates, not independently verified findings.
- AI extraction may miss context or misclassify a problem; source-level review is required before manager circulation.
- The weekly workflow produces a new report artifact; it does not yet merge new findings into a persistent historical master dataset.
- The scheduled workflow must be activated on the default branch with API secrets configured.
