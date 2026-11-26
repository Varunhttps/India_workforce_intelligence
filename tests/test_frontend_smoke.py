import ast
import json
import tempfile
from pathlib import Path
import unittest

from frontend.demo_data import load_demo_findings


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

    def test_dashboard_weekly_trends_uses_numeric_count(self):
        app_path = Path(__file__).resolve().parents[1] / "frontend" / "app.py"
        source = app_path.read_text(encoding="utf-8")
        self.assertIn('st.subheader("Weekly Trends")', source)
        self.assertIn('pd.to_numeric(trends["Weeks Seen"]', source)
        self.assertIn('"Industry", "Workforce Problem", "Supporting Sources", "Weeks Seen"', source)

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
        self.assertIn("mark_bar()", source)
        self.assertIn('mark_text(align="left", dx=5)', source)
        self.assertIn('"Recent findings"', source)
        self.assertIn('"Change"', source)
        self.assertIn("st.altair_chart", source)
        self.assertIn("has_comparison = False", source)
        self.assertIn("only one month available; ranked by counts", source)
        self.assertIn("Bar labels show counts only.", source)

    def test_dashboard_hides_research_run_health_panel(self):
        app_path = Path(__file__).resolve().parents[1] / "frontend" / "app.py"
        source = app_path.read_text(encoding="utf-8")
        self.assertNotIn('st.subheader("Research run health")', source)
        self.assertNotIn('health_cols[2].metric("Research freshness", freshness)', source)
        self.assertNotIn("fetch_latest_research_run_health", source)
        self.assertIn('[data-testid="stToolbar"] {visibility: hidden; height: 0;}', source)


if __name__ == "__main__":
    unittest.main()
