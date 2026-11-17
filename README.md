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
5. Classify source domains using transparent heuristics; these labels are prioritization hints, not endorsements.
6. Publish the manager-facing report to one persistent Google spreadsheet.
7. Update a persistent JSONL history so findings can be compared across weekly runs.

Search-result dates are stored separately from publication dates stated in source material. Search country is not treated as proof of actual finding geography. Findings still need human review before external circulation.

## Google Sheets setup

The weekly workflow writes into the same Google spreadsheet on every run; it clears and refreshes the report tabs rather than creating a new spreadsheet each week.

1. Create a Google Cloud project and enable the **Google Sheets API**.
2. Create a service account and generate a JSON key.
3. Create one Google spreadsheet and copy its spreadsheet ID from its URL (the text between `/d/` and `/edit`).
4. Share that spreadsheet with the service account's email address and grant **Editor** access.
5. Add these GitHub repository Actions secrets under **Settings → Secrets and variables → Actions**:
   - `GOOGLE_SHEET_ID`: spreadsheet ID from the Google Sheets URL.
   - `GOOGLE_SERVICE_ACCOUNT_JSON`: complete JSON key contents (keep it secret; never commit it).
   - Existing `TAVILY_API_KEY` and `GEMINI_API_KEY` remain required.

The workflow refreshes these tabs in the same spreadsheet:
- **Run Overview**
- **Workforce Findings**
- **New Findings**
- **Recurring Findings**
- **Source Register**
- **Research Summary**

The Source Register includes the requested source-tracking fields: Source ID, Source Title, Source URL, Source Type, Publisher / Author, Industry, Publication Date, Access Date, Source Credibility, Key Information and Related Research IDs, plus collection and verification status. Publisher / Author is left blank unless the source data explicitly identifies it; credibility starts as Pending review rather than being invented. Source URLs are stored as direct URLs.

## Weekly automation

GitHub Actions runs every Monday at 06:00 UTC (11:30 India Standard Time). Manual runs support all three research modes. The workflow requires `contents: write` permission to commit updates to `data/findings_history.jsonl`, as well as the four API/Google Sheets secrets listed above. If Google credentials or spreadsheet access are missing, the run fails visibly rather than silently reporting a successful publication.

## Local setup and tests

Python 3.10+ recommended.

```bash
pip install -r requirements.txt
export TAVILY_API_KEY="your-key"
export GEMINI_API_KEY="your-key"
export GOOGLE_SHEET_ID="your-spreadsheet-id"
export GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account", ...}'
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python main.py --mode manufacturing --max-sources-per-industry 3 --publish-google-sheets
```

Available modes: `manufacturing`, `other_industries`, `all_industries`.

## Current limitations

- Tavily results are candidates, not endorsements or independently verified sources.
- Verbatim quote matching confirms that a supporting excerpt exists in the collected text; it does not prove that the model's full interpretation is correct.
- Geography validation is conservative but still needs human review for ambiguous references and regional attribution.
- History identifies recurring records using text, industry, country and source URL; it does not establish that a workforce problem has been resolved when it disappears from later searches.
- Research coverage depends on search-engine indexing, source accessibility, API limits and the selected candidate-source cap.
- Human review remains required before presenting findings as confirmed facts to management.

## LinkedIn source handling

LinkedIn is a discovery channel inside the existing pipeline, not a separate agent. The agent uses search-engine indexing to discover public LinkedIn post/article URLs and only attempts ordinary public-page collection; it does not scrape logged-in content, profiles, contact details or private data. Access restrictions or login walls are recorded as collection failures. Every accepted LinkedIn finding carries `source_platform=LinkedIn` and the original direct LinkedIn `source_url`; the pipeline attaches attribution from source metadata rather than asking the language model to reproduce it. Findings remain candidates requiring human review.


## Streamlit frontend

Run the frontend locally from the repository root:

```bash
pip install -r requirements.txt
streamlit run frontend/app.py
```

Configure Streamlit secrets (or environment variables) for `GOOGLE_SHEET_ID` and `GOOGLE_SERVICE_ACCOUNT_JSON` to read the four tabs. To enable the **Start Research** control, also configure `GITHUB_TOKEN` with permission to dispatch repository Actions workflows. Do not commit these credentials. The control currently supports the existing research scopes (Manufacturing, Other Industries, All Industries), an optional country filter (blank means global) and the source cap per industry. The pipeline's existing discovery channels are web search and public, search-indexed LinkedIn.

The dashboard displays distinct problem counts by industry, the four data tabs, and a link to open the full spreadsheet. Research findings and generated opportunity mappings are candidates for human review, not verified market conclusions or approved Nexplan product commitments.
