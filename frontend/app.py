"""Streamlit frontend for Global Workforce Intelligence."""
import os
import sys
from pathlib import Path
from datetime import date, timedelta

import altair as alt
import gspread
import pandas as pd
import requests
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from workforce_intelligence.dashboard_filters import industry_options, filter_frames_by_industry, weekly_statuses
from workforce_intelligence.skill_trends import analyze_skill_trends
from workforce_intelligence.manager_actions import recommend_manager_actions
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

SHEET_NAMES = ["Source Register", "Market Research", "Market Insights & Trends", "Product Feature Opportunities"]
LOAD_SHEET_NAMES = [*SHEET_NAMES, "Weekly Trends"]


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
    for name in LOAD_SHEET_NAMES:
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
    with st.sidebar:
        st.divider()
        st.header("Dashboard filters")
        selected_industry = st.selectbox("Filter by industry", industry_options(data))
        data = filter_frames_by_industry(data, selected_industry)
        st.caption("The selected industry filter applies to tables and metrics with industry data; source-register rows without an industry remain visible.")
    findings = data["Market Research"].copy()
    sources = data["Source Register"]
    insights = data["Market Insights & Trends"]
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
            st.subheader("Top 5 Industries Facing Workforce Planning Challenges")
            st.bar_chart(industry_counts, height=300)

    st.subheader("Most Critical Workforce Planning Challenges")
    problem_counts = findings["Identified Problem"].dropna().value_counts().head(10)
    if not problem_counts.empty:
        st.bar_chart(problem_counts, height=320)
    else:
        st.info("Workforce challenge rankings will appear when findings are available.")

    st.subheader("Workforce Planning Challenges - Top 10")
    monthly_source = findings.copy()
    date_candidates = ["Research Date", "Latest Week", "Last Seen", "First Seen"]
    trend_date = pd.Series(pd.NaT, index=monthly_source.index, dtype="datetime64[ns]")
    for date_col in date_candidates:
        if date_col in monthly_source.columns:
            parsed = pd.to_datetime(monthly_source[date_col], errors="coerce")
            trend_date = trend_date.fillna(parsed)
    monthly_source["_trend_month"] = trend_date.dt.to_period("M")
    monthly_source = monthly_source.dropna(subset=["_trend_month", "Identified Problem"])
    if not monthly_source.empty:
        monthly_counts = monthly_source.groupby(["_trend_month", "Identified Problem"]).size().unstack(fill_value=0)
        month_order = sorted(monthly_counts.index)
        monthly_counts = monthly_counts.reindex(month_order)
        has_comparison = False
        month_number = lambda period: period.year * 12 + period.month
        last_four = month_order[-4:]
        last_two = month_order[-2:]
        if len(last_four) == 4 and all(
            month_number(next_month) - month_number(previous_month) == 1
            for previous_month, next_month in zip(last_four, last_four[1:])
        ):
            recent_months = last_four[-2:]
            prior_months = last_four[:2]
            recent_totals = monthly_counts.loc[recent_months].sum()
            prior_totals = monthly_counts.loc[prior_months].sum()
            change = recent_totals.subtract(prior_totals, fill_value=0)
            has_comparison = True
            period_label = "recent two months vs previous two months"
        elif len(last_two) == 2 and month_number(last_two[-1]) - month_number(last_two[-2]) == 1:
            recent_totals = monthly_counts.iloc[-1]
            prior_totals = monthly_counts.iloc[-2]
            change = recent_totals.subtract(prior_totals, fill_value=0)
            has_comparison = True
            period_label = "latest month vs previous month"
        else:
            recent_totals = monthly_counts.iloc[-1]
            change = pd.Series(None, index=monthly_counts.columns, dtype="object")
            period_label = (
                "calendar month gaps prevent comparison"
                if len(month_order) >= 2
                else "only one month available; ranked by counts"
            )

        rank_by_change = False
        if has_comparison:
            rising = change[change > 0].sort_values(ascending=False)
            if not rising.empty:
                emerging_names = rising.head(10).index
                rank_by_change = True
                ranking = f"Ranked by increase ({period_label})"
            else:
                emerging_names = recent_totals.sort_values(ascending=False).head(10).index
                ranking = f"No challenges increased ({period_label}); shown by recent counts"
        else:
            emerging_names = recent_totals.sort_values(ascending=False).head(10).index
            ranking = (
                "Calendar month gaps prevent comparison; ranked by latest month counts"
                if len(month_order) >= 2
                else "Date history is limited; ranked by available counts"
            )

        chart_data = pd.DataFrame({
            "Challenge": emerging_names,
            "Recent findings": [int(recent_totals.get(name, 0)) for name in emerging_names],
            "Change": [int(change.get(name, 0)) if has_comparison else None for name in emerging_names],
        }).head(10).reset_index(drop=True)
        chart_data["Rank"] = range(1, len(chart_data) + 1)
        chart_data["Display Challenge"] = chart_data.apply(
            lambda row: f"{int(row['Rank']):02d}  {row['Challenge']}", axis=1
        )
        chart_sort = alt.EncodingSortField(field="Rank", order="ascending")
        chart_data["Label"] = chart_data.apply(
            lambda row: (
                f"{int(row['Recent findings'])}  (Δ {int(row['Change']):+d})"
                if has_comparison else f"{int(row['Recent findings'])}"
            ), axis=1
        )
        max_value = max(1, int(chart_data["Recent findings"].max()))
        x_scale = alt.Scale(domain=[0, max_value * 1.25])
        bars = alt.Chart(chart_data).mark_bar(size=22, cornerRadiusEnd=4).encode(
            x=alt.X("Recent findings:Q", title="Recent observation count", scale=x_scale),
            y=alt.Y("Display Challenge:N", sort=chart_sort, title=None),
            tooltip=["Challenge:N", "Recent findings:Q", "Change:Q"],
        )
        labels = alt.Chart(chart_data).mark_text(align="left", dx=6, fontWeight="bold").encode(
            x=alt.X("Recent findings:Q", scale=x_scale),
            y=alt.Y("Display Challenge:N", sort=chart_sort),
            text="Label:N",
        )
        caption = ranking + (" · Bar labels show recent count and change." if has_comparison else " · Bar labels show counts only.")
        st.caption(caption)
        st.altair_chart((bars + labels).properties(height=max(320, 34 * len(chart_data))), use_container_width=True)
    else:
        st.info("Emerging workforce challenges will appear when findings include research dates.")

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

    trends = data.get("Weekly Trends", pd.DataFrame()).copy()
    if not trends.empty and "Weeks Seen" in trends.columns:
        trends["Weeks Seen"] = pd.to_numeric(trends["Weeks Seen"], errors="coerce").fillna(0).astype(int)
    st.subheader("Emerging Skills & Workforce Trends")
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
        display_skill_columns = ["skill", "trend", "source_count", "industry_count", "country_count", "weeks_observed", "manufacturing_records", "industries", "countries"]
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
            if name == "Product Feature Opportunities":
                frame = frame.drop(columns=["Workforce Planning Area"], errors="ignore")
            st.dataframe(frame, use_container_width=True, hide_index=True)
    st.link_button("Open full Google Spreadsheet", sheet_url)

st.caption("Research findings and product opportunities are AI-assisted candidates and require human review.")
