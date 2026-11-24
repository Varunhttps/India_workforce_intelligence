import ast
from pathlib import Path
import unittest


class FrontendSmokeTests(unittest.TestCase):
    def test_streamlit_app_parses(self):
        app_path = Path(__file__).resolve().parents[1] / "frontend" / "app.py"
        ast.parse(app_path.read_text(encoding="utf-8"), filename=str(app_path))

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
        self.assertNotIn("Opportunity Changes", tabs)

    def test_dashboard_weekly_trends_uses_numeric_count(self):
        app_path = Path(__file__).resolve().parents[1] / "frontend" / "app.py"
        source = app_path.read_text(encoding="utf-8")
        self.assertIn('st.subheader("Weekly Trends")', source)
        self.assertIn('pd.to_numeric(trends["Weeks Seen"]', source)
        self.assertIn('"Industry", "Workforce Problem", "Supporting Sources", "Weeks Seen"', source)

    def test_dashboard_removes_requested_sections_and_shows_top_five_first(self):
        app_path = Path(__file__).resolve().parents[1] / "frontend" / "app.py"
        source = app_path.read_text(encoding="utf-8")
        self.assertIn("Top 5 industries facing workforce problems", source)
        self.assertNotIn("Weekly evidence momentum", source)
        self.assertNotIn("Emerging industries by evidence volume and problem diversity", source)
        self.assertNotIn("Country × industry coverage matrix", source)
        self.assertNotIn("Benchmark gaps", source)
        self.assertIn('st.subheader("Global Workforce Signals")', source)
        top_five_index = source.index("Top 5 industries facing workforce problems")
        weekly_changes_index = source.index('st.subheader(f"Weekly research changes')
        self.assertLess(top_five_index, weekly_changes_index)

    def test_dashboard_hides_research_run_health_panel(self):
        app_path = Path(__file__).resolve().parents[1] / "frontend" / "app.py"
        source = app_path.read_text(encoding="utf-8")
        self.assertNotIn('st.subheader("Research run health")', source)
        self.assertNotIn('health_cols[2].metric("Research freshness", freshness)', source)
        self.assertNotIn("fetch_latest_research_run_health", source)
        self.assertIn('[data-testid="stToolbar"] {visibility: hidden; height: 0;}', source)

    def test_evidence_integrity_audit_uses_unfiltered_workbook_data(self):
        app_path = Path(__file__).resolve().parents[1] / "frontend" / "app.py"
        source = app_path.read_text(encoding="utf-8")
        snapshot_index = source.index("integrity_data = data")
        filter_index = source.index("data = filter_frames_by_industry(data, selected_industry)")
        audit_index = source.index("integrity = audit_evidence_integrity(")
        self.assertLess(snapshot_index, filter_index)
        self.assertGreater(audit_index, filter_index)
        audit_call = source[audit_index:audit_index + 400]
        self.assertIn('integrity_data["Market Research"]', audit_call)
        self.assertIn('integrity_data["Source Register"]', audit_call)

    def test_dashboard_displays_evidence_integrity_audit(self):
        app_path = Path(__file__).resolve().parents[1] / "frontend" / "app.py"
        source = app_path.read_text(encoding="utf-8")
        self.assertIn("audit_evidence_integrity", source)
        self.assertIn('st.subheader("Evidence integrity & traceability")', source)
        self.assertIn("integrity[\"details_truncated\"]", source)
        self.assertIn("ID / source-link mismatches", source)



if __name__ == "__main__":
    unittest.main()
