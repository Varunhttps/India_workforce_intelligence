# Global Workforce Intelligence Agent

A global public-source research agent that identifies and classifies reported workforce problems. Manufacturing is the primary research focus; users can also explore other industries or run an all-industry scan. The agent identifies problems and does not generate solutions.

## Research modes
- **Manufacturing Research** (default): automotive, electronics, semiconductors, machinery, chemicals, pharmaceuticals, food and beverage, textiles, metals and aerospace manufacturing.
- **Explore Other Industries**: construction, healthcare, IT, logistics, retail, hospitality, education, energy, agriculture and financial services.
- **All Industries**: both groups.

## Pipeline
1. Discover candidate public sources using Tavily, including a dedicated LinkedIn-indexed search channel within the same research pipeline.
2. Collect accessible HTML and PDF documents with public-network URL checks, redirect limits and download-size caps.
3. Extract reported workforce problems using Gemini.
4. Require a verbatim source excerpt for every accepted finding; the excerpt is checked against collected text and is not exported as an Evidence column.
5. Classify source domains using transparent heuristics (government, multilateral, academic, research/consulting, possible industry body or unclassified); these labels are prioritization hints, not endorsements.\n6. Export a manager-facing Excel workbook with Run Overview, Workforce Findings, New Findings, Recurring Findings, Source Register and Research Summary sheets.
7. Update a persistent JSONL history so findings can be compared across weekly runs.

Search-result dates are stored separately from publication dates stated in source material. Search country is not treated as proof of actual finding geography. Findings still need human review before external circulation.

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

To use a persistent history file locally:

```bash
PYTHONPATH=src python main.py --mode manufacturing --max-sources-per-industry 3 --history-path data/findings_history.jsonl
```

## Weekly automation
The GitHub Actions workflow is configured for Mondays at 06:00 UTC (11:30 India Standard Time). It requires repository Actions secrets named `TAVILY_API_KEY` and `GEMINI_API_KEY`. Manual runs support all three research modes.

A run uploads the Excel report as an artifact retained for 30 days and commits updates to `data/findings_history.jsonl` on `main`. The workflow requires `contents: write` permission. The history contains public-source finding metadata and source URLs; do not place private or sensitive material in it.

## Workbook fields
The findings sheet contains problem type, description, country, region, industry, sub-industry, company, source name, source URL, source platform, publication date, data period and review status. LinkedIn findings retain the direct original LinkedIn URL; search-engine result URLs are never substituted. LinkedIn pages that cannot be publicly collected remain inaccessible candidates in the Source Register and are not treated as traceable findings. Evidence, Confidence and HR Category columns are intentionally excluded. The source register records source metadata, collection status, search-result date, source publication date, heuristic source class and verification status.

## Current limitations
- Tavily results are candidates, not endorsements or independently verified sources.
- Verbatim quote matching confirms that a supporting excerpt exists in the collected text; it does not prove that the model's full interpretation is correct.
- Geography validation is conservative but still needs human review for ambiguous references and regional attribution.
- History identifies recurring records using text, industry, country and source URL; it does not establish that a workforce problem has been resolved when it disappears from later searches.
- Research coverage depends on search-engine indexing, source accessibility, API limits and the selected candidate-source cap.
- Human review remains required before presenting findings as confirmed facts to management.

## LinkedIn source handling
LinkedIn is a discovery channel inside the existing pipeline, not a separate agent. The agent uses search-engine indexing to discover public LinkedIn post/article URLs and only attempts ordinary public-page collection; it does not scrape logged-in content, profiles, contact details or private data. Access restrictions or login walls are recorded as collection failures. Every accepted LinkedIn finding carries `source_platform=LinkedIn` and the original direct LinkedIn `source_url`; the pipeline attaches attribution from source metadata rather than asking the language model to reproduce it. Findings remain candidates requiring human review.
