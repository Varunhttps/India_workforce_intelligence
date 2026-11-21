# Demo walkthrough and portfolio narrative

## 3–5 minute demo

1. **Research scope (30 sec):** Show Manufacturing, Other Industries, and All Industries. Explain global coverage and the manufacturing emphasis.
2. **Research overview (30 sec):** Show cumulative findings, new/recurring counts, industries and countries. Explain the selected industry filter.
3. **Source Register (45 sec):** Open a source link and show source platform, collection status and heuristic credibility. Explain that an accepted finding has a source excerpt checked against collected text, but this is not a human fact-check.
4. **Country coverage (30 sec):** Show explicit country attribution, regions and the optional benchmark gap list. Explain that search target does not equal finding geography.
5. **Weekly trends (45 sec):** Show new/active/not-observed and source/country momentum. Emphasize that evidence growth is a research-coverage signal—not proof of worsening conditions.
6. **Emerging skills (30 sec):** Show keyword-mapped clusters and explain scores as breadth/recency heuristics.
7. **Manager action intelligence (45 sec):** Open one ranked item, its score rationale, recommended next step and source links. Show that the score is explainable and not a validated severity score.
8. **Opportunity priorities (30 sec):** Show the opportunity track and priority filters; explain mappings are candidates for investigation rather than approved business decisions.

## Architecture story

- **Discovery:** Tavily search across industry research and public source channels, with a global scope or optional country search.
- **Collection:** bounded public-document fetching with HTTP(S), public-address validation, redirect limits, content-size limits and HTML/PDF extraction.
- **Extraction:** Gemini proposes findings from collected documents; accepted findings require a verbatim supporting excerpt.
- **Quality:** URL normalization, duplicate merging, relevance/source/date/geography annotations and human-review caveats.
- **Persistence:** append-only JSONL history plus the persistent Google Sheets report.
- **Analysis:** weekly comparisons, country coverage, skill clusters, opportunity priorities and manager action recommendations.
- **Presentation:** Streamlit dashboard with industry filters and Google OIDC allowlist gate.

## Portfolio explanation (use your own words)

"I built a global workforce research pipeline that turns public reporting into traceable workforce signals. The pipeline discovers sources, collects bounded public documents, extracts source-supported findings with an LLM, deduplicates and annotates them, tracks week-over-week evidence, and publishes to Google Sheets and a Streamlit dashboard. I added decision-support layers for country coverage, emerging skills, manager actions and product opportunities. I deliberately keep scoring explainable and label evidence-volume changes as research coverage rather than workforce severity."

## Live demo checklist

- Refresh the sheet and confirm the latest research run is current.
- Pick 2–3 examples with accessible original source links and clear geography.
- Avoid showing an example with ambiguous source attribution unless you use it to explain limitations.
- Verify login and research dispatch permissions with a test account.
- Do not display API keys, service-account JSON, OAuth client secrets or personal data.
- Have a static screenshot/demo dataset ready in case API limits or the live sheet fail.
