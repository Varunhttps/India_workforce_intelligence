"""Streamlit frontend for the Global Workforce Intelligence project."""
import os
import requests
import streamlit as st
import gspread
import pandas as pd

st.set_page_config(page_title="Global Workforce Intelligence", page_icon="🌍", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 1.8rem; max-width: 1500px;}
[data-testid="stMetric"] {background: #f4f7fb; padding: 16px; border-radius: 12px;}
</style>
""", unsafe_allow_html=True)

SHEET_NAMES = ["Source Register", "Market Research", "Market Insights & Trends", "Product Feature Opportunities"]


@st.cache_data(ttl=90)
def load_sheets():
    credentials = st.secrets.get("GOOGLE_SERVICE_ACCOUNT_JSON") or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    sheet_id = st.secrets.get("GOOGLE_SHEET_ID") or os.getenv("GOOGLE_SHEET_ID")
    if not credentials or not sheet_id:
        return None
    import json
    client = gspread.service_account_from_dict(json.loads(credentials))
    book = client.open_by_key(sheet_id)
    data = {}
    for name in SHEET_NAMES:
        try:
            values = book.worksheet(name).get_all_records()
            data[name] = pd.DataFrame(values)
        except gspread.WorksheetNotFound:
            data[name] = pd.DataFrame()
    return data, book.url


def trigger_research(mode, country, limit):
    token = st.secrets.get("GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("Configure GITHUB_TOKEN in Streamlit secrets with Actions write permission.")
    url = "https://api.github.com/repos/Varunhttps/India_workforce_intelligence/actions/workflows/weekly-research.yml/dispatches"
    inputs = {"mode": mode, "max_sources_per_industry": str(limit)}
    if country.strip():
        inputs["country_searched"] = country.strip()
    response = requests.post(
        url, headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        json={"ref": "main", "inputs": inputs}, timeout=30
    )
    if response.status_code != 204:
        raise RuntimeError(f"GitHub rejected the research request ({response.status_code}): {response.text[:500]}")


st.title("🌍 Global Workforce Intelligence")
st.caption("Research • Workforce challenges • Market trends • Nexplan opportunities")

with st.sidebar:
    st.header("Research controls")
    scope = st.selectbox("Research scope", ["Manufacturing", "Other industries", "All industries"])
    mode = {"Manufacturing": "manufacturing", "Other industries": "other_industries",
            "All industries": "all_industries"}[scope]
    country = st.text_input("Country (optional)", placeholder="Leave blank for global research")
    limit = st.number_input("Sources per industry", min_value=1, max_value=20, value=3)
    st.caption("The current research pipeline searches the web and public, search-indexed LinkedIn sources.")
    if st.button("▶ Start Research", type="primary", use_container_width=True):
        try:
            trigger_research(mode, country, int(limit))
            st.success("Research workflow dispatched. Check GitHub Actions for its live status.")
            st.link_button("View workflow runs", "https://github.com/Varunhttps/India_workforce_intelligence/actions")
        except Exception as exc:
            st.error(str(exc))

st.subheader("Research overview")
try:
    loaded = load_sheets()
except Exception as exc:
    loaded = None
    st.error(f"Could not read Google Sheets: {exc}")

if not loaded:
    st.info("Connect the Google Sheet using GOOGLE_SHEET_ID and GOOGLE_SERVICE_ACCOUNT_JSON in Streamlit secrets.")
else:
    data, sheet_url = loaded
    findings = data["Market Research"]
    sources = data["Source Register"]
    opportunities = data["Product Feature Opportunities"]
    industries = findings["Industry"].dropna().nunique() if "Industry" in findings else 0
    countries = findings["Country"].dropna().nunique() if "Country" in findings else 0
    a, b, c, d = st.columns(4)
    a.metric("Distinct research records", len(findings))
    b.metric("Industries", industries)
    c.metric("Sources", len(sources))
    d.metric("Countries identified", countries)

    st.subheader("Top 5 industries by distinct workforce problems")
    insights = data["Market Insights & Trends"]
    if not insights.empty and {"Section", "Industry", "Distinct Problem Count"}.issubset(insights.columns):
        consolidated = insights[
            insights["Section"].astype(str).str.casefold() == "consolidated workforce challenges"
        ].copy()
        consolidated["Distinct Problem Count"] = pd.to_numeric(
            consolidated["Distinct Problem Count"], errors="coerce"
        ).fillna(0)
        ranking = (consolidated.groupby("Industry", as_index=False)["Distinct Problem Count"]
                   .sum().sort_values("Distinct Problem Count", ascending=False).head(5))
    elif not findings.empty and {"Industry", "Identified Problem"}.issubset(findings.columns):
        # Fallback for older spreadsheets that predate the consolidated insights tab.
        ranking = (findings.groupby("Industry")["Identified Problem"].nunique()
                   .sort_values(ascending=False).head(5).rename("Distinct Problem Count").reset_index())
    else:
        ranking = pd.DataFrame(columns=["Industry", "Distinct Problem Count"])

    if not ranking.empty:
        st.bar_chart(ranking.set_index("Industry"))
        st.dataframe(ranking, use_container_width=True, hide_index=True)
        st.subheader("Top 5 industry research reports")
        for industry in ranking["Industry"].tolist():
            with st.expander(str(industry)):
                report = findings[findings["Industry"].astype(str) == str(industry)].copy()
                if report.empty:
                    st.info("No detailed research records are available for this industry yet.")
                else:
                    display_columns = [c for c in [
                        "Identified Problem", "Problem Description", "Business Impact",
                        "Country", "Region", "Research Date", "Research Status", "Source URL"
                    ] if c in report.columns]
                    st.dataframe(report[display_columns], use_container_width=True, hide_index=True)
    else:
        st.info("No research findings have been published yet.")

    tabs = st.tabs(SHEET_NAMES)
    for tab, name in zip(tabs, SHEET_NAMES):
        with tab:
            frame = data[name]
            st.dataframe(frame, use_container_width=True, hide_index=True)
    st.link_button("Open full Google Spreadsheet", sheet_url)

st.caption("Research findings and product opportunities are AI-assisted candidates and require human review.")
