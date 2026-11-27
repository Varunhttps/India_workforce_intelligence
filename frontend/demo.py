"""Offline demo dashboard. Run: streamlit run frontend/demo.py"""
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from workforce_intelligence.skill_trends import analyze_skill_trends
from workforce_intelligence.manager_actions import recommend_manager_actions
from workforce_intelligence.opportunity_prioritization import build_opportunity_priorities
from frontend.demo_data import load_demo_findings, build_emerging_challenge_chart_data

st.set_page_config(page_title="Global Workforce Intelligence · Demo", page_icon="🌍", layout="wide")
st.title("🌍 Global Workforce Intelligence")
st.caption("Offline portfolio demo · Snapshot of committed research history · No API credentials required")
st.warning("Demo snapshot only. Findings are research candidates, not independently verified conclusions. This view is read-only and does not trigger research.")

records = load_demo_findings()
if not records:
    st.error("No demo findings found in data/findings_history.jsonl.")
    st.stop()

df = pd.DataFrame(records)
industries_all = sorted(df["Industry"].dropna().unique().tolist())
with st.sidebar:
    st.header("Demo filters")
    chosen = st.selectbox("Industry", ["All industries"] + industries_all)
    if chosen != "All industries":
        df = df[df["Industry"] == chosen].copy()

source_count = df["Source URL"].loc[df["Source URL"].astype(str).str.strip() != ""].nunique()
country_count = df.loc[df["Country"] != "Not specified", "Country"].nunique()
latest_recorded = pd.to_datetime(df["Last Seen"], errors="coerce").max()
latest_recorded_label = latest_recorded.strftime("%d %b %Y") if pd.notna(latest_recorded) else "Unknown"
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Research findings", len(df))
k2.metric("Industries", df["Industry"].nunique())
k3.metric("Countries attributed", country_count)
k4.metric("Unique source links", source_count)
k5.metric("Latest finding observed", latest_recorded_label)
st.caption("Latest finding date is based on the snapshot's Last Seen field and respects the selected industry filter.")

def render_labeled_horizontal_bars(data, category, value, axis_title, height=300):
    chart_data = data.copy().sort_values(value, ascending=False)
    chart_data["Label"] = chart_data[value].astype(int).astype(str)
    sort_order = alt.EncodingSortField(field=value, order="descending")
    max_value = max(1, int(chart_data[value].max()))
    scale = alt.Scale(domain=[0, max_value * 1.25])
    bars = alt.Chart(chart_data).mark_bar().encode(
        x=alt.X(f"{value}:Q", title=axis_title, scale=scale),
        y=alt.Y(f"{category}:N", sort=sort_order, title=None),
        tooltip=[f"{category}:N", f"{value}:Q"],
    )
    labels = alt.Chart(chart_data).mark_text(align="left", dx=5).encode(
        x=alt.X(f"{value}:Q", scale=scale),
        y=alt.Y(f"{category}:N", sort=sort_order),
        text="Label:N",
    )
    st.altair_chart((bars + labels).properties(height=max(height, 34 * len(chart_data))), use_container_width=True)


st.subheader("Top 5 Industries Facing Workforce Planning Challenges")
industry_counts = (
    df.dropna(subset=["Industry", "Identified Problem"])
    .groupby("Industry")["Identified Problem"]
    .nunique()
    .sort_values(ascending=False)
    .head(5)
)
if not industry_counts.empty:
    industry_chart_data = industry_counts.rename_axis("Industry").reset_index(name="Challenge types")
    render_labeled_horizontal_bars(
        industry_chart_data, "Industry", "Challenge types",
        "Distinct workforce challenge types", height=260
    )
    st.caption("Ranked by distinct challenge types identified in the snapshot.")
else:
    st.info("Industry rankings will appear when findings are available.")

st.subheader("Most Critical Workforce Planning Challenges")
problem_counts = df["Identified Problem"].dropna().value_counts().head(10)
if not problem_counts.empty:
    critical_chart_data = problem_counts.rename_axis("Challenge").reset_index(name="Findings")
    render_labeled_horizontal_bars(
        critical_chart_data, "Challenge", "Findings",
        "Finding count", height=320
    )
    st.caption("Counts represent records in the snapshot—not independently verified severity.")
else:
    st.info("Workforce challenge rankings will appear when findings are available.")

st.subheader("Emerging Workforce Planning Challenges · Top 10")
emerging_chart_data, emerging_caption = build_emerging_challenge_chart_data(
    df.to_dict("records"), top_n=10
)
if emerging_chart_data:
    emerging_frame = pd.DataFrame(emerging_chart_data)
    sort_order = alt.EncodingSortField(field="Rank score", order="descending")
    max_value = max(1, int(emerging_frame["Weekly observations"].max()))
    scale = alt.Scale(domain=[0, max_value * 1.25])
    bars = alt.Chart(emerging_frame).mark_bar().encode(
        x=alt.X("Weekly observations:Q", title="Weekly observations in recent period", scale=scale),
        y=alt.Y("Challenge:N", sort=sort_order, title=None),
        tooltip=["Challenge:N", "Weekly observations:Q", "Change:Q"],
    )
    labels = alt.Chart(emerging_frame).mark_text(align="left", dx=5).encode(
        x=alt.X("Weekly observations:Q", scale=scale),
        y=alt.Y("Challenge:N", sort=sort_order),
        text="Label:N",
    )
    st.altair_chart((bars + labels).properties(height=max(320, 34 * len(emerging_frame))), use_container_width=True)
    st.caption(emerging_caption + " · Labels show counts and change when a comparison is possible.")
else:
    st.info("Emerging workforce challenges will appear when findings are available.")

st.subheader("Emerging skills and workforce signals")
skill_inputs = [{
    "problem_type": row["Identified Problem"], "description": row["Problem Description"],
    "industry": row["Industry"], "country": row["Country"], "source_url": row["Source URL"],
    "first_seen": row["First Seen"], "last_seen": row["Last Seen"],
    "weeks_seen": [w.strip() for w in str(row["Observation Weeks"]).split(",") if w.strip()],
} for _, row in df.iterrows()]
skills = analyze_skill_trends(skill_inputs)
if skills:
    skill_df = pd.DataFrame(skills)
    display_skill_columns = [column for column in skill_df.columns if column != "signal_score"]
    st.dataframe(skill_df[display_skill_columns], use_container_width=True, hide_index=True)
else:
    st.info("No keyword-mapped skills were detected in this snapshot.")

st.subheader("Manager action intelligence")
manager = recommend_manager_actions(df, pd.DataFrame())
if manager:
    manager_df = pd.DataFrame(manager)
    st.dataframe(manager_df, use_container_width=True, hide_index=True)
    for _, item in manager_df.head(5).iterrows():
        with st.expander(f"{item['Priority']} · {item['Industry']} · {item['Workforce Problem']}"):
            st.write("**Suggested action:**", item.get("Recommended Next Step"))
            st.write("**Rationale:**", item.get("Score Rationale"))
            for url in item.get("Evidence URLs", []):
                st.markdown(f"- [Open source]({url})")
else:
    st.info("Manager action suggestions need more populated data.")

st.subheader("Opportunity priorities")
opportunities = build_opportunity_priorities(df, pd.DataFrame(), pd.DataFrame())
if opportunities:
    opp_df = pd.DataFrame(opportunities)
    st.dataframe(opp_df, use_container_width=True, hide_index=True)
else:
    st.info("No mapped product-capability opportunities are included in this offline snapshot. Use the connected dashboard for workbook-mapped opportunity priorities.")

st.subheader("Raw research snapshot")
display_cols = ["Industry", "Identified Problem", "Problem Description", "Country", "Source Name", "Source Platform", "Weeks Seen", "Source URL"]
st.dataframe(df[display_cols], use_container_width=True, hide_index=True)
