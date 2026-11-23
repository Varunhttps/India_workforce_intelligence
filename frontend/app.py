"""Streamlit frontend for Global Workforce Intelligence."""
import os
import sys
from pathlib import Path
from datetime import date, timedelta

import gspread
import pandas as pd
import requests
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from workforce_intelligence.signal_momentum import analyze_signal_momentum, rank_emerging_industries

st.set_page_config(page_title="Global Workforce Intelligence", page_icon="🌍", layout="wide")

# Private-access gate: configure Streamlit OIDC (Google) and an email allowlist.
def _allowed_emails():
    configured = st.secrets.get("ALLOWED_EMAILS", os.getenv("ALLOWED_EMAILS", ""))
    if isinstance(configured, str):
        return {email.strip().lower() for email in configured.split(",") if email.strip()}
    return {str(email).strip().lower() for email in configured if str(email).strip()}

def _require_auth():
    require_auth = str(os.getenv("REQUIRE_AUTH", "true")).lower() not in {"0", "false", "no"}
    if not require_auth:
        st.warning("Authentication is disabled for this local development session.")
        return
    allowed = _allowed_emails()
    if not allowed:
        st.error("Private access is not configured. Add ALLOWED_EMAILS to Streamlit secrets before deploying.")
        st.stop()
    if not st.user.is_logged_in:
        st.title("🌍 Global Workforce Intelligence")
        st.write("Private workforce intelligence portal. Sign in with an invited account to continue.")
        st.button("Sign in with Google", on_click=st.login, args=("google",), type="primary")
        st.stop()
    email = str(st.user.email or "").lower()
    if email not in allowed:
        st.error("This account is not on the approved access list.")
        st.button("Sign out", on_click=st.logout)
        st.stop()

_require_auth()

st.markdown("""
<style>
.block-container {padding-top: 1.35rem; max-width: 1540px;}
[data-testid="stMetric"] {background: #f4f7fb; padding: 16px; border: 1px solid #e3e9f2; border-radius: 14px;}
[data-testid="stMetricLabel"] {font-weight: 600;}
[data-testid="stSidebar"] {border-right: 1px solid #e6eaf0;}
h1 {letter-spacing: -0.035em;}
[data-testid="stTabs"] button {font-weight: 600;}
/* Hide Streamlit's developer toolbar for end users. */
[data-testid="stToolbar"] {visibility: hidden; height: 0;}
</style>
""", unsafe_allow_html=True)

SHEET_NAMES = ["Source Register", "Market Research", "Market Insights & Trends", "Product Feature Opportunities", "Weekly Trends"]


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


def week_start(today=None):
    today = today or date.today()
    return today - timedelta(days=today.weekday())


st.title("🌍 Global Workforce Intelligence")
st.caption("Global workforce signals · Weekly trend intelligence · Staffing & enterprise planning opportunities")

with st.sidebar:
    st.header("Research controls")
    scope = st.selectbox(
        "Research scope", ["All industries", "Manufacturing", "Other industries"], index=0
    )
    mode = {"Manufacturing": "manufacturing", "Other industries": "other_industries",
            "All industries": "all_industries"}[scope]
    country = st.text_input("Countries (optional)", placeholder="India, Germany, Japan — blank for global research")
    st.caption("Searches up to 8 results per query across web and public, search-indexed LinkedIn, filters weak relevance scores and unrelated titles/snippets, and prioritizes stronger publisher types. Multiple countries broaden coverage.")
    if st.button("▶ Start Research", type="primary", use_container_width=True):
        try:
            trigger_research(mode, country, 8)
            st.success("Research refresh started. New insights will appear once the update is complete.")
        except Exception as exc:
            st.error("We couldn't start the research refresh. Please try again later or contact your dashboard administrator.")

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
    findings = data["Market Research"].copy()
    sources = data["Source Register"]
    insights = data["Market Insights & Trends"]

    if not findings.empty and "Weekly Status" in findings.columns:
        weekly_status = findings["Weekly Status"].fillna("").astype(str)
    else:
        weekly_status = pd.Series([""] * len(findings), index=findings.index)

    new_week = findings[weekly_status == "New this week"].copy() if not findings.empty else findings.copy()
    recurring_week = findings[weekly_status == "Recurring this week"].copy() if not findings.empty else findings.copy()
    not_observed = findings[weekly_status == "Last seen before this week"].copy() if not findings.empty else findings.copy()

    industries = findings["Industry"].dropna().nunique() if "Industry" in findings else 0
    countries = findings["Country"].dropna().nunique() if "Country" in findings else 0
    latest_research_date = ""
    if "Research Date" in findings.columns and not findings.empty:
        parsed_dates = pd.to_datetime(findings["Research Date"], errors="coerce")
        if parsed_dates.notna().any():
            latest_research_date = parsed_dates.max().date().isoformat()
    a, b, c, d, e = st.columns(5)
    a.metric("Historical findings", len(findings))
    b.metric("New this week", len(new_week))
    c.metric("Recurring this week", len(recurring_week))
    d.metric("Industries", industries)
    e.metric("Countries", countries)
    if latest_research_date:
        st.caption(f"Latest research date recorded: **{latest_research_date}** · Data refreshes automatically after the weekly research run.")

    st.subheader(f"Weekly research changes · Week of {week_start().isoformat()}")
    st.caption("Weekly status is based on first-seen and last-seen week metadata. Older findings are retained; not seeing them in the latest research does not mean the problem has been resolved.")
    weekly_tabs = st.tabs(["New this week", "Recurring this week", "Last seen before this week"])
    weekly_frames = [new_week, recurring_week, not_observed]
    for tab, frame in zip(weekly_tabs, weekly_frames):
        with tab:
            if frame.empty:
                st.info("No records in this category for the current weekly period, or the sheet has not yet been refreshed with weekly metadata.")
            else:
                columns = [c for c in [
                    "Industry", "Identified Problem", "Problem Description", "Country",
                    "Region", "Source URL"
                ] if c in frame.columns]
                st.dataframe(frame[columns], use_container_width=True, hide_index=True)

    st.subheader("Weekly trend signals")
    trends = data.get("Weekly Trends", pd.DataFrame()).copy()
    if not trends.empty and "Signal Status" in trends.columns:
        x, y, z = st.columns(3)
        x.metric("New problems", int((trends["Signal Status"] == "New this week").sum()))
        y.metric("Active this week", int((trends["Signal Status"] == "Active this week").sum()))
        z.metric("Not observed this week", int((trends["Signal Status"] == "Not observed this week").sum()))
        st.caption("Signals are aggregated by industry and workforce problem. 'Not observed this week' does not mean resolved.")
        trend_cols = [c for c in ["Industry", "Workforce Problem", "Signal Status", "Country Count", "Countries", "Supporting Source Count"] if c in trends.columns]
        st.dataframe(trends[trend_cols], use_container_width=True, hide_index=True)
    else:
        st.info("Weekly trend signals will appear after the cumulative history is published.")

    st.subheader("Weekly evidence momentum")
    momentum_records = []
    if not findings.empty:
        for _, finding in findings.iterrows():
            raw_weeks = str(finding.get("Weeks Seen") or "")
            weeks_seen = [week.strip() for week in raw_weeks.split(",") if week.strip()]
            momentum_records.append({
                "industry": finding.get("Industry"),
                "problem_type": finding.get("Identified Problem"),
                "source_url": finding.get("Source URL"),
                "weeks_seen": weeks_seen,
                "first_seen": finding.get("First Seen"),
                "last_seen": finding.get("Last Seen"),
                "country": finding.get("Country"),
            })
    momentum_rows = analyze_signal_momentum(momentum_records)
    if momentum_rows:
        momentum_frame = pd.DataFrame(momentum_rows)
        momentum_columns = ["industry", "problem_type", "previous_source_count", "current_source_count", "source_delta", "trend", "country_count", "countries"]
        st.caption("Changes in supporting source coverage, not confirmed changes in workforce severity. 'Not observed this week' may reflect research coverage.")
        st.dataframe(momentum_frame[momentum_columns], use_container_width=True, hide_index=True)
        industry_rank = rank_emerging_industries(momentum_rows)
        if industry_rank:
            rank_frame = pd.DataFrame(industry_rank)
            rank_columns = ["rank", "industry", "current_sources", "distinct_problem_count", "increasing_problems", "staffing_candidates", "planning_candidates"]
            st.markdown("**Emerging industries by evidence volume and problem diversity**")
            st.dataframe(rank_frame[rank_columns], use_container_width=True, hide_index=True)
    else:
        st.info("Weekly momentum will populate once historical findings with week metadata are available.")

    st.subheader("Cumulative research overview")
    e, f, g = st.columns(3)
    e.metric("Sources", len(sources))
    f.metric("Countries identified", countries)
    g.metric("Historical records", len(findings))

    st.subheader("Top 5 industries by distinct workforce problems")
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
                        "Country", "Region", "Research Date", "Weekly Status", "Source URL"
                    ] if c in report.columns]
                    st.dataframe(report[display_columns], use_container_width=True, hide_index=True)
    else:
        st.info("No research findings have been published yet.")

    tabs = st.tabs(SHEET_NAMES)
    for tab, name in zip(tabs, SHEET_NAMES):
        with tab:
            frame = data[name]
            if name == "Source Register":
                hide = ["Collection Status", "Key Information", "Evidence / Supporting Information", "Review Notes"]
                frame = frame.drop(columns=[col for col in hide if col in frame.columns], errors="ignore")
            elif name == "Market Research":
                hide = ["Evidence / Supporting Information", "Supporting Evidence", "Review Notes", "First Seen", "Last Seen", "Weeks Seen", "Observation Weeks", "Latest Week", "Last Week"]
                frame = frame.drop(columns=[col for col in hide if col in frame.columns], errors="ignore")
            st.dataframe(frame, use_container_width=True, hide_index=True)
    # Spreadsheet link is intentionally omitted from the general-user dashboard.

st.caption("Research findings and product opportunities are AI-assisted candidates and require human review.")
