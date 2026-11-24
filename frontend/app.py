"""Streamlit frontend for Global Workforce Intelligence."""
import os
import sys
from pathlib import Path
from datetime import date, timedelta

import gspread
import pandas as pd
import requests
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from workforce_intelligence.dashboard_filters import industry_options, filter_frames_by_industry, weekly_statuses
from workforce_intelligence.opportunity_prioritization import build_opportunity_priorities
from workforce_intelligence.skill_trends import analyze_skill_trends
from workforce_intelligence.country_coverage import summarize_country_coverage, build_country_industry_matrix
from workforce_intelligence.manager_actions import recommend_manager_actions
from workforce_intelligence.evidence_integrity import audit_evidence_integrity
from frontend.private_access import (
    parse_allowed_emails,
    missing_auth_keys as missing_auth_settings,
    is_email_allowed,
)

st.set_page_config(page_title="Global Workforce Intelligence", page_icon="🌍", layout="wide")

# Private-access gate: Google OIDC and an explicit email allowlist are always required.
def _allowed_emails():
    configured = st.secrets.get("ALLOWED_EMAILS", os.getenv("ALLOWED_EMAILS", ""))
    return parse_allowed_emails(configured)

def _require_auth():
    allowed = _allowed_emails()
    if not allowed:
        st.error("Private access is not configured. Add ALLOWED_EMAILS to Streamlit secrets before deploying.")
        st.stop()
    # Streamlit's st.user auth state raises KeyError when OIDC is not configured.
    # Validate the required settings first so an incomplete deployment fails safely.
    auth_config = st.secrets.get("auth", {})
    missing_auth = missing_auth_settings(auth_config)
    if missing_auth:
        st.error("Google sign-in is not configured yet. Add the required [auth] settings to Streamlit secrets using the deployment guide, then reboot the app.")
        st.caption("Missing authentication settings: " + ", ".join(missing_auth))
        st.stop()
    if not st.user.is_logged_in:
        st.title("🌍 Global Workforce Intelligence")
        st.write("Private workforce intelligence portal. Sign in with an invited account to continue.")
        st.button("Sign in with Google", on_click=st.login, type="primary")
        st.stop()
    email = str(st.user.email or "")
    if not is_email_allowed(email, allowed):
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
/* Remove developer toolbar links from public-facing dashboard. */
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
    st.caption("Uses your selected source cap per industry across web and public, search-indexed LinkedIn; filters weak relevance and unrelated results, then prioritizes stronger publisher types. Multiple countries broaden coverage.")
    source_limit = 8
    if st.button("▶ Start Research", type="primary", use_container_width=True):
        try:
            trigger_research(mode, country, source_limit)
            st.success("Research workflow dispatched successfully.")
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
    integrity_data = data  # Preserve the full workbook for cross-sheet audits before applying UI filters.
    with st.sidebar:
        st.divider()
        st.header("Dashboard filters")
        selected_industry = st.selectbox("Filter by industry", industry_options(data))
        data = filter_frames_by_industry(data, selected_industry)
        st.caption("The selected industry filter applies to tables and metrics with industry data; source-register rows without an industry remain visible.")
    findings = data["Market Research"].copy()
    sources = data["Source Register"]
    insights = data["Market Insights & Trends"]
    st.subheader("Evidence integrity & traceability")
    integrity = audit_evidence_integrity(
        integrity_data["Market Research"],
        integrity_data["Source Register"],
        integrity_data.get("Product Feature Opportunities", pd.DataFrame()),
    )
    integrity_metrics = integrity["metrics"]
    integrity_cols = st.columns(5)
    integrity_cols[0].metric("Missing research IDs", integrity_metrics["findings_missing_research_id"])
    integrity_cols[1].metric(
        "Missing / invalid source URLs",
        integrity_metrics["findings_missing_source_url"] + integrity_metrics["findings_invalid_source_url"],
    )
    integrity_cols[2].metric("URLs not in Source Register", integrity_metrics["findings_urls_not_in_source_register"] + integrity_metrics["opportunity_urls_not_in_source_register"])
    integrity_cols[3].metric("ID / source-link mismatches", integrity_metrics["findings_source_id_mismatch"] + integrity_metrics["source_register_link_mismatch"] + integrity_metrics["opportunity_research_source_mismatch"])
    integrity_cols[4].metric("Duplicate IDs", integrity_metrics["duplicate_research_ids"] + integrity_metrics["duplicate_source_ids"])
    st.caption("Audit covers the full workbook, independent of the industry filter. These checks validate cross-sheet IDs and links only; they do not validate source truth, article interpretation or the severity of a workforce claim.")
    if integrity["warning_count"]:
        st.warning(f"{integrity['warning_count']} warning-level traceability issue(s) detected. Review the details before relying on affected records.")
    else:
        st.success("No warning-level cross-sheet traceability issues were found in the loaded records.")
    if integrity["info_count"]:
        st.caption(f"{integrity['info_count']} informational source-register record(s) are not linked to research IDs.")
    if integrity["issues"]:
        with st.expander("Inspect traceability findings", expanded=False):
            st.dataframe(pd.DataFrame(integrity["issues"]), use_container_width=True, hide_index=True)
            if integrity["details_truncated"]:
                st.caption(f"Showing the first {len(integrity['issues'])} of {integrity['total_issue_details']} traceability details.")


    weekly_status = weekly_statuses(findings, current_week=week_start().isoformat())

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

    if not findings.empty and "Industry" in findings.columns and "Identified Problem" in findings.columns:
        industry_counts = (
            findings.dropna(subset=["Industry", "Identified Problem"])
            .groupby("Industry")["Identified Problem"]
            .nunique()
            .sort_values(ascending=False)
            .head(5)
        )
        if not industry_counts.empty:
            st.subheader("Top 5 industries facing workforce problems")
            st.caption("Ranked by the number of distinct workforce problem types identified in the current research.")
            st.bar_chart(industry_counts, height=300)


    st.subheader("Global Workforce Signals")
    st.caption("Counts are based on explicit country attribution in findings—not the countries targeted during search.")
    coverage_rows = summarize_country_coverage(findings.to_dict("records"))
    coverage_frame = pd.DataFrame(coverage_rows)
    if not coverage_frame.empty:
        total_countries = int((coverage_frame["Findings"] > 0).sum())
        represented_regions = coverage_frame.loc[coverage_frame["Findings"] > 0, "Region"].nunique()
        coverage_metrics = st.columns(2)
        coverage_metrics[0].metric("Countries with findings", total_countries)
        coverage_metrics[1].metric("Regions represented", represented_regions)
        covered = coverage_frame[coverage_frame["Findings"] > 0].copy()
        if not covered.empty:
            chart_frame = covered.set_index("Country")["Findings"].head(10)
            st.bar_chart(chart_frame, height=280)
            st.dataframe(covered, use_container_width=True, hide_index=True)
    else:
        st.info("Country coverage will appear after findings with explicit country attribution are published.")

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
                    "Region", "First Seen", "Latest Week", "Source URL"
                ] if c in frame.columns]
                st.dataframe(frame[columns], use_container_width=True, hide_index=True)

    st.subheader("Weekly Trends")
    trends = data.get("Weekly Trends", pd.DataFrame()).copy()
    if not trends.empty and "Weeks Seen" in trends.columns:
        trends["Weeks Seen"] = pd.to_numeric(trends["Weeks Seen"], errors="coerce").fillna(0).astype(int)
        trends = trends.sort_values("Weeks Seen", ascending=False)
        trend_cols = [col for col in [
            "Industry", "Workforce Problem", "Supporting Sources", "Weeks Seen"
        ] if col in trends.columns]
        st.caption("Weeks Seen is the numeric count of distinct weeks this workforce problem appears in the research history. It indicates observation persistence, not problem severity.")
        st.dataframe(trends[trend_cols], use_container_width=True, hide_index=True)
    else:
        st.info("Weekly trend counts will appear after the cumulative history is published.")

    st.subheader("Emerging Skills & Workforce Trends")
    st.caption("Global skill clusters inferred from findings. Signal score reflects research breadth and recency—not measured labor-market demand.")
    skill_records = []
    if not findings.empty:
        for _, finding in findings.iterrows():
            weeks_raw = str(finding.get("Observation Weeks") or "")
            skill_records.append({
                "problem_type": finding.get("Identified Problem"),
                "description": finding.get("Problem Description"),
                "industry": finding.get("Industry"),
                "country": finding.get("Country"),
                "source_url": finding.get("Source URL"),
                "first_seen": finding.get("First Seen"),
                "last_seen": finding.get("Latest Week") or finding.get("Last Seen"),
                "weeks_seen": [w.strip() for w in weeks_raw.split(",") if w.strip()],
            })
    skill_rows = analyze_skill_trends(skill_records)
    if skill_rows:
        skill_frame = pd.DataFrame(skill_rows)
        skill_metrics = st.columns(4)
        skill_metrics[0].metric("Skill clusters", len(skill_rows))
        skill_metrics[1].metric("Emerging signals", int((skill_frame["trend"] == "Emerging signal").sum()))
        skill_metrics[2].metric("Persistent signals", int((skill_frame["trend"] == "Persistent signal").sum()))
        skill_metrics[3].metric("Manufacturing-linked", int(skill_frame["manufacturing_focus"].sum()))
        st.bar_chart(skill_frame.set_index("skill")["signal_score"].head(12), height=300)
        display_skill_columns = ["skill", "trend", "signal_score", "source_count", "industry_count", "country_count", "weeks_observed", "manufacturing_records", "industries", "countries"]
        st.dataframe(skill_frame[display_skill_columns], use_container_width=True, hide_index=True)
    else:
        st.info("Skill signals will appear when published findings match skill-cluster keywords.")
    st.subheader("Manager Action & Opportunity Intelligence")
    st.caption("Ranked investigation suggestions from research evidence. Scores measure research coverage and recency—not verified workforce severity.")
    manager_rows = recommend_manager_actions(findings, trends if "trends" in locals() else pd.DataFrame())
    if manager_rows:
        manager_frame = pd.DataFrame(manager_rows)
        top_count = min(5, len(manager_frame))
        top_manager = manager_frame.head(top_count)
        manager_metrics = st.columns(3)
        manager_metrics[0].metric("Action candidates", len(manager_frame))
        manager_metrics[1].metric("Validate now", int((manager_frame["Priority"] == "Act / validate now").sum()))
        manager_metrics[2].metric("Investigate next", int((manager_frame["Priority"] == "Investigate next").sum()))
        st.bar_chart(top_manager.set_index("Workforce Problem")["Rank Score"], height=300)
        st.dataframe(manager_frame[["Rank Score", "Priority", "Industry", "Workforce Problem", "Manager Action", "Source Count", "Country Count", "Latest Evidence", "Weekly Momentum"]], use_container_width=True, hide_index=True)
        for _, manager_action in manager_frame.head(10).iterrows():
            with st.expander(f"{manager_action['Priority']} · {manager_action['Industry']} · {manager_action['Workforce Problem']}"):
                st.write("**Recommended next step:** " + str(manager_action["Recommended Next Step"]))
                st.write("**Scoring rationale:** " + str(manager_action["Score Rationale"]))
                st.write("**Countries:** " + ", ".join(manager_action["Countries"]) if manager_action["Countries"] else "No country attribution")
                for evidence_url in manager_action["Evidence URLs"]:
                    st.markdown(f"- [{evidence_url}]({evidence_url})")
    else:
        st.info("Manager recommendations will appear once research findings are available.")

    st.subheader("Opportunity Priorities")
    priority_rows = build_opportunity_priorities(
        findings, data.get("Product Feature Opportunities", pd.DataFrame()), sources
    )
    if priority_rows:
        priority_frame = pd.DataFrame(priority_rows)
        filter_cols = st.columns(3)
        track_options = ["All tracks", *sorted(priority_frame["Track"].dropna().unique().tolist())]
        track_choice = filter_cols[0].selectbox("Opportunity track", track_options, key="opportunity_track_filter")
        priority_options = ["All priorities", "High priority", "Investigate", "Monitor"]
        priority_choice = filter_cols[1].selectbox("Priority level", priority_options, key="opportunity_priority_filter")
        country_options = ["All countries", *sorted({country for row in priority_rows for country in str(row.get("Countries") or "").split(",") if country.strip()})]
        country_choice = filter_cols[2].selectbox("Evidence country", country_options, key="opportunity_country_filter")
        filtered_priorities = priority_frame.copy()
        if track_choice != "All tracks":
            filtered_priorities = filtered_priorities[filtered_priorities["Track"] == track_choice]
        if priority_choice != "All priorities":
            filtered_priorities = filtered_priorities[filtered_priorities["Priority"] == priority_choice]
        if country_choice != "All countries":
            filtered_priorities = filtered_priorities[filtered_priorities["Countries"].astype(str).str.contains(country_choice, case=False, regex=False)]
        score_columns = ["Score", "Priority", "Track", "Industry", "Market Need", "Capability", "Source Count", "Country Count", "Latest Evidence"]
        st.caption("Scores are transparent heuristics based on evidence breadth, recency, reported impact, source credibility and mapped actionability. They are prioritization aids—not proof of shortage severity.")
        st.dataframe(filtered_priorities[score_columns], use_container_width=True, hide_index=True)
        for _, opportunity in filtered_priorities.iterrows():
            title = f"{opportunity['Priority']} · {opportunity['Industry']} · {opportunity['Market Need']}"
            with st.expander(title):
                st.write(opportunity["Suggested Feature"])
                st.write("**Business value:** " + str(opportunity["Business Value"] or "Not specified in mapping"))
                st.write("**Countries:** " + str(opportunity["Countries"] or "Not identified"))
                st.write("**Evidence source URLs:**")
                for source_url in str(opportunity["Supporting Source URLs"] or "").split(","):
                    source_url = source_url.strip()
                    if source_url:
                        st.markdown(f"- [{source_url}]({source_url})")
                st.write("**Score breakdown (out of 100):**")
                st.json(opportunity["Score Breakdown"])
                st.caption(opportunity["Scoring Note"])
    else:
        st.info("Mapped opportunities will appear after research and opportunity mapping are available.")

    st.subheader("Cumulative research overview")
    e, f, g = st.columns(3)
    e.metric("Sources", len(sources))
    f.metric("Countries identified", countries)
    g.metric("Historical records", len(findings))

    tabs = st.tabs(SHEET_NAMES)
    for tab, name in zip(tabs, SHEET_NAMES):
        with tab:
            frame = data[name]
            if name == "Source Register":
                hide = ["Collection Status", "Key Information", "Evidence / Supporting Information", "Review Notes"]
                frame = frame.drop(columns=[col for col in hide if col in frame.columns], errors="ignore")
            elif name == "Market Research":
                hide = ["Evidence / Supporting Information", "Supporting Evidence", "Review Notes", "Occurrences", "Weekly Status", "Research Status", "Interpretation Status", "Review Status"]
                frame = frame.drop(columns=[col for col in hide if col in frame.columns], errors="ignore")
            st.dataframe(frame, use_container_width=True, hide_index=True)
    st.link_button("Open full Google Spreadsheet", sheet_url)

st.caption("Research findings and product opportunities are AI-assisted candidates and require human review.")
