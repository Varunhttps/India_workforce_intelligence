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
        self.assertEqual(len(tabs), 6)
        self.assertIn("Weekly Trends", tabs)
        self.assertIn("Opportunity Changes", tabs)

    def test_dashboard_weekly_trends_uses_numeric_count(self):
        app_path = Path(__file__).resolve().parents[1] / "frontend" / "app.py"
        source = app_path.read_text(encoding="utf-8")
        self.assertIn('st.subheader("Weekly Trends · Weeks Seen")', source)
        self.assertIn('pd.to_numeric(trends["Weeks Seen"]', source)
        self.assertIn('"Industry", "Workforce Problem", "Supporting Sources", "Weeks Seen"', source)

    def test_dashboard_momentum_and_skill_signals_use_observation_week_dates(self):
        app_path = Path(__file__).resolve().parents[1] / "frontend" / "app.py"
        source = app_path.read_text(encoding="utf-8")
        self.assertIn('finding.get("Observation Weeks")', source)
        self.assertIn('finding.get("Latest Week") or finding.get("Last Seen")', source)
        self.assertNotIn('finding.get("Weeks Seen") or ""', source)

    def test_dashboard_has_independent_opportunity_changes_section(self):
        app_path = Path(__file__).resolve().parents[1] / "frontend" / "app.py"
        source = app_path.read_text(encoding="utf-8")
        opportunity_section = source.index('    st.subheader("Opportunity changes")')
        trends_section = source.index('    st.subheader("Weekly Trends · Weeks Seen")')
        self.assertGreater(opportunity_section, trends_section)
        self.assertIn("# Opportunity Changes is independent of Weekly Trends", source)


if __name__ == "__main__":
    unittest.main()
