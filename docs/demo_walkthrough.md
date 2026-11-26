# Demo walkthrough and portfolio narrative

## 3–5 minute offline portfolio demo

Use the credential-free snapshot demo from the repository root:

```bash
pip install -r requirements.txt
streamlit run frontend/demo.py
```

1. **Set the context (20 sec):** Explain that this is a read-only snapshot of committed research history. It does not trigger research, call external APIs, or require OAuth/Google Sheets credentials.
2. **Summary metrics (30 sec):** Point out the cumulative research-finding count, number of industries, countries attributed, unique source links, and latest recorded finding date. Select an industry and note that the metrics update with the filter.
3. **Industry/problem distribution (45 sec):** Compare the findings-by-industry chart and workforce-problem categories. Clarify that these reflect the collected snapshot, not a statistical estimate of the global labor market.
4. **Country coverage (30 sec):** Show the explicit country attribution table. Explain that the pipeline does not infer a country from the search target alone.
5. **Emerging skills (40 sec):** Show keyword-mapped skill signals and explain that the mapping is heuristic; it is not a validated demand forecast.
6. **Manager action intelligence (45 sec):** Open one priority item and show its suggested next step, rationale and source links. Explain that suggestions are decision support, not approved actions or verified severity ratings.
7. **Opportunity priorities (30 sec):** Show any mapped opportunity rows. If the snapshot has none, explain that this view needs mapped data and that the connected dashboard uses workbook-backed opportunity priorities.
8. **Traceability (30 sec):** Finish with the raw research snapshot table and open an original source link. Emphasize that findings are candidates for human review.

## Architecture story

- **Discovery:** Tavily searches public research and indexed public source channels.
- **Collection:** Bounded fetching of accessible public HTML/PDF content with network-safety checks.
- **Extraction:** Gemini proposes workforce findings; accepted findings require a supporting excerpt checked against collected text.
- **Quality:** URL normalization, duplicate handling, relevance/source/date/geography checks and human-review caveats.
- **Persistence:** Append-only JSONL research history and a persistent Google Sheets report.
- **Analysis:** Country coverage, keyword-mapped skills, manager actions and opportunity-priority heuristics.
- **Presentation:** A connected Streamlit dashboard for authorized users and a separate read-only offline snapshot demo.

## Portfolio explanation (use your own words)

“I built a global workforce research pipeline that turns public reporting into traceable workforce signals. It discovers sources, collects bounded public documents, extracts source-supported findings with an LLM, deduplicates and annotates records, maintains cumulative history, and publishes to Google Sheets and a Streamlit dashboard. The offline demo lets people explore a committed snapshot without credentials or research dispatch. I added decision-support layers for country coverage, emerging skills, manager actions and product opportunities, while keeping their heuristic limitations visible.”

## Offline demo checklist

- Run the demo from the repository root using the command above.
- Confirm the snapshot loads and an industry filter updates the displayed metrics and tables.
- Choose 2–3 examples with accessible source URLs and clear geography.
- Avoid presenting heuristic scores or evidence volume as validated workforce severity.
- Keep a screenshot or snapshot demo available if live services are unavailable.
- Do not display API keys, service-account JSON, OAuth secrets or personal data.

## Connected dashboard / live research checklist

- Configure Streamlit Google OIDC and the explicit email allowlist.
- Configure Google Sheet ID and service-account credentials; grant the service account access to the intended spreadsheet.
- Confirm the dashboard reads the correct tabs and handles empty/missing data.
- Test an allowlisted sign-in and verify that an unallowlisted account is blocked.
- Only configure the research-dispatch token if the **Start Research** action is intentionally enabled.
- Before a controlled live run, confirm API credentials, publishing destination and run scope.
- Verify the run status and spreadsheet update; never treat “sources discovered” as proof that findings were extracted or published.
