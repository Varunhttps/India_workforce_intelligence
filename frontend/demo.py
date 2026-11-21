"""Offline demo dashboard. Run: streamlit run frontend/demo.py"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from workforce_intelligence.country_coverage import summarize_country_coverage
from workforce_intelligence.skill_trends import analyze_skill_trends
from workforce_intelligence.manager_actions import recommend_manager_actions
from workforce_intelligence.opportunity_prioritization import build_opportunity_priorities
from frontend.demo_data import load_demo_findings

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

source_count = df["Source URL"].nunique()
country_count = df.loc[df["Country"] != "Not specified", "Country"].nunique()
k1, k2, k3, k4 = st.columns(4)
k1.metric("Research findings", len(df))
k2.metric("Industries", df["Industry"].nunique())
k3.metric("Countries attributed", country_count)
k4.metric("Unique source links", source_count)

st.subheader("Findings by industry")
counts = df["Industry"].value_counts().sort_values(ascending=False)
st.bar_chart(counts, height=300)

st.subheader("Workforce problem categories")
problem_counts = df["Identified Problem"].value_counts().head(12)
st.bar_chart(problem_counts, height=300)

st.subheader("Country coverage")
coverage = pd.DataFrame(summarize_country_coverage(records))
if not coverage.empty:
    coverage = coverage.sort_values("Findings", ascending=False)
    st.dataframe(coverage, use_container_width=True, hide_index=True)
else:
    st.info("No explicit country attribution in the current demo snapshot.")

st.subheader("Emerging skills and workforce signals")
skill_inputs = [{
    "problem_type": row["Identified Problem"], "description": row["Problem Description"],
    "industry": row["Industry"], "country": row["Country"], "source_url": row["Source URL"],
    "first_seen": row["First Seen"], "last_seen": row["Last Seen"],
    "weeks_seen": [w.strip() for w in str(row["Weeks Seen"]).split(",") if w.strip()],
} for _, row in df.iterrows()]
skills = analyze_skill_trends(skill_inputs)
if skills:
    skill_df = pd.DataFrame(skills)
    st.bar_chart(skill_df.set_index("skill")["signal_score"].head(10), height=300)
    st.dataframe(skill_df, use_container_width=True, hide_index=True)
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

st.subheader("Raw research snapshot")
display_cols = ["Industry", "Identified Problem", "Problem Description", "Country", "Source Name", "Source Platform", "First Seen", "Last Seen", "Source URL"]
st.dataframe(df[display_cols], use_container_width=True, hide_index=True)
