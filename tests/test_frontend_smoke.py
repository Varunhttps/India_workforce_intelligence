import ast
from pathlib import Path
import unittest


class FrontendSmokeTests(unittest.TestCase):
    def test_streamlit_app_parses(self):
        app_path = Path(__file__).resolve().parents[1] / "frontend" / "app.py"
        ast.parse(app_path.read_text(encoding="utf-8"), filename=str(app_path))

    def test_legacy_sheet_loader_lists_all_dashboard_tabs(self):
        loader_path = Path(__file__).resolve().parents[1] / "frontend" / "data_loader.py"
        namespace = {}
        # Extract and evaluate only the literal TABS assignment to avoid importing
        # frontend service dependencies in this smoke test.
        source = loader_path.read_text(encoding="utf-8")
        module = ast.parse(source, filename=str(loader_path))
        tabs_node = next(node for node in module.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "TABS" for target in node.targets))
        tabs = ast.literal_eval(tabs_node.value)
        self.assertEqual(len(tabs), 6)
        self.assertIn("Weekly Trends", tabs)
        self.assertIn("Opportunity Changes", tabs)


if __name__ == "__main__":
    unittest.main()
