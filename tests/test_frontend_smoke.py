import ast
import json
import tempfile
from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest

from frontend.demo_data import load_demo_findings, build_emerging_challenge_chart_data


class FrontendSmokeTests(unittest.TestCase):
    def test_streamlit_app_parses(self):
        app_path = Path(__file__).resolve().parents[1] / "frontend" / "app.py"
        ast.parse(app_path.read_text(encoding="utf-8"), filename=str(app_path))

    def test_offline_demo_parses_and_has_no_research_dispatch(self):
        demo_path = Path(__file__).resolve().parents[1] / "frontend" / "demo.py"
        source = demo_path.read_text(encoding="utf-8")
        module = ast.parse(source, filename=str(demo_path))
        calls = {ast.unparse(node.func) for node in ast.walk(module) if isinstance(node, ast.Call)}
        self.assertNotIn("st.button", calls)
        self.assertNotIn("requests.post", calls)
        self.assertNotIn("trigger_research", source)
        self.assertNotIn("GITHUB_TOKEN", source)

    def test_offline_demo_runs_without_streamlit_runtime_exceptions(self):
        demo_path = Path(__file__).resolve().parents[1] / "frontend" / "demo.py"
        app_test = AppTest.from_file(str(demo_path)).run()
        self.assertEqual(len(app_test.exception), 0)

    def test_offline_demo_loader_maps_history_and_skips_invalid_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = Path(tmp) / "findings.jsonl"
            record = {
                "industry": "Manufacturing",
                "problem_type": "Skills gap",
                "description": "Shortage of technicians.",
                "country": "India",
                "region": "Gujarat",
                "source_name": "Sample report",
                "source_url": "https://example.org/report",
                "source_platform": "Web",
                "first_seen": "2026-11-16",
                "last_seen": "2026-11-25",
                "weeks_seen": ["2026-11-16", "2026-11-25", "invalid"],
                "occurrences": 3,
            }
            history_path.write_text(json.dumps(record) + chr(10) + "invalid-json" + chr(10) + "[]" + chr(10), encoding="utf-8")
            records = load_demo_findings(history_path)

        self.assertEqual(len(records), 1)
        result = records[0]
        self.assertEqual(result["Industry"], "Manufacturing")
        self.assertEqual(result["Identified Problem"], "Skills gap")
        self.assertEqual(result["Country"], "India")
        self.assertEqual(result["Source URL"], "https://example.org/report")
        self.assertEqual(result["Observation Weeks"], "2026-11-16, 2026-11-23")
        self.assertEqual(result["Weeks Seen"], 2)
        self.assertEqual(result["Occurrences"], 3)

    def test_offline_demo_shows_challenge_sections_in_requested_order_and_removes_country_chart(self):
        demo_path = Path(__file__).resolve().parents[1] / "frontend" / "demo.py"
        source = demo_path.read_text(encoding="utf-8")
        sections = [
            'st.subheader("Top 5 Industries Facing Workforce Planning Challenges")',
            'st.subheader("Most Critical Workforce Planning Challenges")',
            'st.subheader("Emerging Workforce Planning Challenges · Top 10")',
        ]
        positions = [source.index(section) for section in sections]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn('st.subheader("Country coverage")', source)
        self.assertNotIn("summarize_country_coverage", source)
        self.assertIn("render_labeled_horizontal_bars", source)
        self.assertIn('mark_text(align="left", dx=5)', source)
        self.assertIn('alt.EncodingSortField(field=value, order="descending")', source)
        self.assertIn('alt.EncodingSortField(field="Rank score", order="descending")', source)
        self.assertIn("Weekly observations in recent period", source)

    def test_emerging_challenges_show_counts_without_fake_delta_for_one_month(self):
        records = [
            {"Identified Problem": "Skills gap", "Observation Weeks": "2026-11-09, 2026-11-16"},
            {"Identified Problem": "Skills gap", "Observation Weeks": "2026-11-16"},
        ]
        rows, caption = build_emerging_challenge_chart_data(records)
        self.assertEqual(rows[0]["Weekly observations"], 3)
        self.assertIsNone(rows[0]["Change"])
        self.assertEqual(rows[0]["Label"], "3")
        self.assertIn("only one month", caption)

    def test_emerging_challenges_do_not_compare_across_missing_calendar_months(self):
        records = [
            {"Identified Problem": "Skills gap", "Observation Weeks": "2026-10-05, 2026-12-07"},
        ]
        rows, caption = build_emerging_challenge_chart_data(records)
        self.assertEqual(rows[0]["Weekly observations"], 1)
        self.assertIsNone(rows[0]["Change"])
        self.assertEqual(rows[0]["Label"], "1")
        self.assertIn("calendar month gaps prevent comparison", caption)

    def test_emerging_challenges_compare_latest_month_to_previous_month(self):
        records = [
            {"Identified Problem": "Talent shortage", "Observation Weeks": "2026-10-05, 2026-11-02"},
            {"Identified Problem": "Talent shortage", "Observation Weeks": "2026-11-02"},
            {"Identified Problem": "Skills gap", "Observation Weeks": "2026-10-05"},
            {"Identified Problem": "Skills gap", "Observation Weeks": "2026-10-05, 2026-11-02"},
        ]
        rows, caption = build_emerging_challenge_chart_data(records)
        self.assertEqual([row["Challenge"] for row in rows], ["Talent shortage"])
        self.assertEqual(rows[0]["Weekly observations"], 2)
        self.assertEqual(rows[0]["Change"], 1)
        self.assertEqual(rows[0]["Label"], "2 (Δ +1)")
        self.assertIn("latest month", caption)

    def test_emerging_challenges_compare_two_month_windows_when_history_is_longer(self):
        records = [
            {"Identified Problem": "Talent shortage", "Observation Weeks": "2026-10-05, 2026-11-02"},
            {"Identified Problem": "Skills gap", "Observation Weeks": "2026-10-05, 2026-11-02, 2026-12-07, 2027-01-04"},
            {"Identified Problem": "Skills gap", "Observation Weeks": "2026-12-07, 2027-01-04"},
        ]
        rows, caption = build_emerging_challenge_chart_data(records)
        self.assertEqual([row["Challenge"] for row in rows], ["Skills gap"])
        self.assertEqual(rows[0]["Weekly observations"], 4)
        self.assertEqual(rows[0]["Change"], 2)
        self.assertEqual(rows[0]["Label"], "4 (Δ +2)")
        self.assertIn("latest two months", caption)

    def test_dashboard_emerging_chart_is_ranked_top_ten_with_labels(self):
        app_path = Path(__file__).resolve().parents[1] / "frontend" / "app.py"
        source = app_path.read_text(encoding="utf-8")
        self.assertIn('}).head(10).reset_index(drop=True)', source)
        self.assertIn('chart_data["Rank"] = range(1, len(chart_data) + 1)', source)
        self.assertIn('"Display Challenge"', source)
        self.assertIn('field="Rank", order="ascending"', source)
        self.assertIn('mark_bar(size=22, cornerRadiusEnd=4)', source)
        self.assertIn('mark_text(align="left", dx=6, fontWeight="bold")', source)
        self.assertIn('text="Label:N"', source)

    def test_streamlit_minimum_version_supports_auth_api(self):
        requirements_path = Path(__file__).resolve().parents[1] / "requirements.txt"
        requirement = next(
            line for line in requirements_path.read_text(encoding="utf-8").splitlines()
            if line.lower().startswith("streamlit")
        )
        self.assertIn(">=1.42", requirement)

    def test_legacy_sheet_loader_lists_all_dashboard_tabs(self):
        loader_path = Path(__file__).resolve().parents[1] / "frontend" / "data_loader.py"
        source = loader_path.read_text(encoding="utf-8")
        module = ast.parse(source, filename=str(loader_path))
        tabs_node = next(node for node in module.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "TABS" for target in node.targets))
        tabs = ast.literal_eval(tabs_node.value)
        self.assertEqual(len(tabs), 5)
        self.assertIn("Weekly Trends", tabs)

    def test_dashboard_weekly_trends_table_removed_but_internal_data_retained(self):
        app_path = Path(__file__).resolve().parents[1] / "frontend" / "app.py"
        source = app_path.read_text(encoding="utf-8")
        self.assertNotIn('st.subheader("Weekly Trends")', source)
        self.assertNotIn('st.dataframe(trends[trend_cols]', source)
        self.assertIn('pd.to_numeric(trends["Weeks Seen"]', source)
        self.assertIn('LOAD_SHEET_NAMES = [*SHEET_NAMES, "Weekly Trends"]', source)

    def test_dashboard_prioritizes_requested_workforce_challenge_sections_and_removes_country_signals(self):
        app_path = Path(__file__).resolve().parents[1] / "frontend" / "app.py"
        source = app_path.read_text(encoding="utf-8")
        sections = [
            'st.subheader("Top 5 Industries Facing Workforce Planning Challenges")',
            'st.subheader("Most Critical Workforce Planning Challenges")',
            'st.subheader("Emerging Workforce Planning Challenges · Top 10")',
        ]
        positions = [source.index(section) for section in sections]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("Global workforce signals · Weekly trend intelligence · Staffing & enterprise planning opportunities", source)
        self.assertNotIn('st.subheader("Global Workforce Signals")', source)
        self.assertNotIn("summarize_country_coverage", source)
        self.assertNotIn("Ranked horizontal bar chart", source)
        self.assertIn("import altair as alt", source)
        self.assertIn("mark_bar(size=22, cornerRadiusEnd=4)", source)
        self.assertIn('mark_text(align="left", dx=6, fontWeight="bold")', source)
        self.assertIn('"Recent findings"', source)
        self.assertIn('"Change"', source)
        self.assertIn("st.altair_chart", source)
        self.assertIn("Display Challenge", source)
        self.assertIn('field="Rank", order="ascending"', source)
        self.assertIn("has_comparison = False", source)
        self.assertIn("only one month available; ranked by counts", source)
        self.assertIn("Bar labels show counts only.", source)
        self.assertNotIn('st.subheader("Opportunity Priorities")', source)

    def test_dashboard_hides_weekly_trends_tab_but_keeps_data_for_logic(self):
        app_path = Path(__file__).resolve().parents[1] / "frontend" / "app.py"
        source = app_path.read_text(encoding="utf-8")
        self.assertIn('SHEET_NAMES = ["Source Register", "Market Research", "Market Insights & Trends", "Product Feature Opportunities"]', source)
        self.assertIn('LOAD_SHEET_NAMES = [*SHEET_NAMES, "Weekly Trends"]', source)
        self.assertIn('for name in LOAD_SHEET_NAMES:', source)
        self.assertNotIn('st.subheader("Weekly Trends")', source)
        self.assertNotIn('st.dataframe(trends[trend_cols]', source)

    def test_product_features_tab_hides_duplicate_workforce_planning_area(self):
        app_path = Path(__file__).resolve().parents[1] / "frontend" / "app.py"
        source = app_path.read_text(encoding="utf-8")
        self.assertIn('if name == "Product Feature Opportunities":', source)
        self.assertIn('frame = frame.drop(columns=["Workforce Planning Area"], errors="ignore")', source)

    def test_dashboard_hides_research_run_health_panel(self):
        app_path = Path(__file__).resolve().parents[1] / "frontend" / "app.py"
        source = app_path.read_text(encoding="utf-8")
        self.assertNotIn('st.subheader("Research run health")', source)
        self.assertNotIn('health_cols[2].metric("Research freshness", freshness)', source)
        self.assertNotIn("fetch_latest_research_run_health", source)
        self.assertIn('[data-testid="stToolbar"] {visibility: hidden; height: 0;}', source)


if __name__ == "__main__":
    unittest.main()
