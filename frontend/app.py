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

from workforce_intelligence.dashboard_filters import industry_options, filter_frames_by_industry
from workforce_intelligence.opportunity_prioritization import build_opportunity_priorities
from workforce_intelligence.skill_trends import analyze_skill_trends
from workforce_intelligence.country_coverage import summarize_country_coverage, build_country_industry_matrix
from workforce_intelligence.manager_actions import recommend_manager_actions
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
    # Streamlit's st.user auth state raises KeyError when OIDC is not configured.
    # Check the required auth secrets first and show a safe setup message instead.
    auth_config = st.secrets.get("auth", {})
    required_auth_keys = {"client_id", "client_secret", "redirect_uri", "cookie_secret"}
    missing_auth = sorted(required_auth_keys - set(auth_config.keys()))
    if missing_auth:
        st.error("Google sign-in is not configured yet. Add the required [auth] settings to Streamlit secrets using the deployment guide, then reboot the app.")
        st.caption("Missing authentication settings: " + ", ".join(missing_auth))
        st.stop()
    if not st.user.is_logged_in:
        st.title("🌍 Global Workforce Intelligence")
        st.write("Private workforce intelligence portal. Sign in with an invited account to continue.")
        st.button("Sign in with Google", on_click=st.login, type="primary")
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
</style>
""", unsafe_allow_html=True)

SHEET_NAMES = ["Source Register", "Market Research", "Market Insights & Trends", "Product Feature Opportunities", "Weekly Trends", "Opportunity Changes"]


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
    with st.sidebar:
        st.divider()
        st.header("Dashboard filters")
        selected_industry = st.selectbox("Filter by industry", industry_options(data))
        data = filter_frames_by_industry(data, selected_industry)
        st.caption("The selected industry filter applies to tables and metrics with industry data; source-register rows without an industry remain visible.")
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

    st.subheader("Global country coverage")
    st.caption("Counts are based on explicit country attribution in findings—not the countries targeted during search.")
    benchmark_text = st.text_input(
        "Optional coverage benchmark countries",
        placeholder="e.g. United States, Germany, Japan, India, Brazil",
        help="Enter countries you want to benchmark. Countries with zero explicitly attributed findings will appear as coverage gaps.",
        key="country_coverage_benchmarks",
    )
    benchmark_countries = [country.strip() for country in benchmark_text.split(",") if country.strip()]
    coverage_rows = summarize_country_coverage(findings.to_dict("records"), target_countries=benchmark_countries)
    coverage_frame = pd.DataFrame(coverage_rows)
    matrix = build_country_industry_matrix(findings.to_dict("records"), target_countries=benchmark_countries)
    matrix_frame = pd.DataFrame(matrix).T.fillna(0).astype(int) if matrix else pd.DataFrame()
    if not coverage_frame.empty:
        total_countries = int((coverage_frame["Findings"] > 0).sum())
        represented_regions = coverage_frame.loc[coverage_frame["Findings"] > 0, "Region"].nunique()
        zero_coverage = int((coverage_frame["Findings"] == 0).sum())
        coverage_metrics = st.columns(3)
        coverage_metrics[0].metric("Countries with findings", total_countries)
        coverage_metrics[1].metric("Regions represented", represented_regions)
        coverage_metrics[2].metric("Benchmark gaps", zero_coverage if benchmark_countries else "—")
        covered = coverage_frame[coverage_frame["Findings"] > 0].copy()
        gaps = coverage_frame[coverage_frame["Findings"] == 0].copy()
        if not covered.empty:
            chart_frame = covered.set_index("Country")["Findings"].head(10)
            st.bar_chart(chart_frame, height=280)
            st.dataframe(covered, use_container_width=True, hide_index=True)
        if benchmark_countries:
            st.markdown("**Countries in your benchmark with no findings**")
            if gaps.empty:
                st.success("All benchmark countries currently have at least one explicitly attributed finding.")
            else:
                st.dataframe(gaps[["Country", "Region"]], use_container_width=True, hide_index=True)
        if not matrix_frame.empty:
            st.markdown("**Country × industry coverage matrix**")
            st.dataframe(matrix_frame, use_container_width=True)
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
                    "Region", "First Seen", "Last Seen", "Weeks Seen", "Source URL"
                ] if c in frame.columns]
                st.dataframe(frame[columns], use_container_width=True, hide_index=True)

    st.subheader("Weekly trend momentum")
    trends = data.get("Weekly Trends", pd.DataFrame()).copy()
    opportunities = data.get("Opportunity Changes", pd.DataFrame()).copy()
    if not trends.empty and "Signal Status" in trends.columns:
        emerging_count = int(trends.get("Emerging Signal", pd.Series(dtype=object)).astype(str).str.lower().isin(["true", "1", "yes"]).sum())
        worsening_count = int(trends.get("Potentially Worsening", pd.Series(dtype=object)).astype(str).str.lower().isin(["true", "1", "yes"]).sum())
        receding_count = int((trends.get("Signal Momentum", pd.Series(dtype=object)) == "Evidence receding").sum())
        a, b, c, d, e = st.columns(5)
        a.metric("New problems", int((trends["Signal Status"] == "New this week").sum()))
        b.metric("Active problems", int((trends["Signal Status"] == "Active this week").sum()))
        c.metric("Emerging signals", emerging_count)
        d.metric("Potentially worsening", worsening_count)
        e.metric("Evidence receding", receding_count)
        st.caption("Source/country growth is a research signal—not proof that the underlying workforce problem worsened. Missing weekly coverage does not mean resolution.")
        trend_cols = [col for col in [
            "Industry", "Workforce Problem", "Signal Status", "Signal Momentum",
            "Emerging Signal", "Potentially Worsening", "Weeks Observed",
            "Sources This Week", "Sources Previous Week", "Source Count Delta",
            "Total Countries", "Countries This Week", "Countries Previous Week",
            "Country Count Delta", "First Seen", "Last Seen"
        ] if col in trends.columns]
        if "Source Count Delta" in trends.columns:
            trends["Source Count Delta"] = pd.to_numeric(trends["Source Count Delta"], errors="coerce").fillna(0)
            trends = trends.sort_values("Source Count Delta", ascending=False)
        st.dataframe(trends[trend_cols], use_container_width=True, hide_index=True)
    else:
        st.info("Weekly trend signals will appear after the cumulative history is published.")

    # Opportunity Changes is independent of Weekly Trends: one tab may be populated before the other.
    st.subheader("Opportunity changes")
    if not opportunities.empty:
        new_opportunities = int(opportunities.get("New This Week", pd.Series(dtype=object)).astype(str).str.lower().isin(["true", "1", "yes"]).sum())
        expanded_opportunities = int(opportunities.get("Expanded Evidence", pd.Series(dtype=object)).astype(str).str.lower().isin(["true", "1", "yes"]).sum())
        opportunity_receding = int((opportunities.get("Change Status", pd.Series(dtype=object)) == "Evidence receded").sum())
        x, y, z = st.columns(3)
        x.metric("New opportunities", new_opportunities)
        y.metric("Expanded evidence", expanded_opportunities)
        z.metric("Evidence receded", opportunity_receding)
        opportunity_cols = [col for col in [
            "Industry", "Market Need", "Capability", "Suggested Feature", "Business Value",
            "Priority", "Change Status", "Weeks Observed", "Sources This Week",
            "Sources Previous Week", "Source Count Delta", "Total Countries",
            "Countries This Week", "Country Count Delta"
        ] if col in opportunities.columns]
        if "Source Count Delta" in opportunities.columns:
            opportunities["Source Count Delta"] = pd.to_numeric(opportunities["Source Count Delta"], errors="coerce").fillna(0)
            opportunities = opportunities.sort_values("Source Count Delta", ascending=False)
        st.dataframe(opportunities[opportunity_cols], use_container_width=True, hide_index=True)
    else:
        st.info("Opportunity changes will appear after the history is published.")

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

    st.subheader("Emerging Skills & Workforce Trends")
    st.caption("Global skill clusters inferred from findings. Signal score reflects research breadth and recency—not measured labor-market demand.")
    skill_records = []
    if not findings.empty:
        for _, finding in findings.iterrows():
            weeks_raw = str(finding.get("Weeks Seen") or "")
            skill_records.append({
                "problem_type": finding.get("Identified Problem"),
                "description": finding.get("Problem Description"),
                "industry": finding.get("Industry"),
                "country": finding.get("Country"),
                "source_url": finding.get("Source URL"),
                "first_seen": finding.get("First Seen"),
                "last_seen": finding.get("Last Seen"),
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
                hide = ["Evidence / Supporting Information", "Supporting Evidence", "Review Notes", "Occurrences", "Weekly Status", "Research Status", "Interpretation Status", "Review Status"]
                frame = frame.drop(columns=[col for col in hide if col in frame.columns], errors="ignore")
            st.dataframe(frame, use_container_width=True, hide_index=True)
    st.link_button("Open full Google Spreadsheet", sheet_url)

st.caption("Research findings and product opportunities are AI-assisted candidates and require human review.")
