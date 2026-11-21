"""Regression test for safe handling of workflow_dispatch inputs."""
from pathlib import Path
import unittest


class WorkflowInputSafetyTests(unittest.TestCase):
    def test_dispatch_inputs_are_not_interpolated_into_run_script(self):
        workflow_path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "weekly-research.yml"
        workflow = workflow_path.read_text(encoding="utf-8")
        run_script = workflow.split("run: |", 1)[1].split("\n      - name:", 1)[0]

        for input_name in ("country_searched", "mode", "max_sources_per_industry"):
            self.assertNotIn(f"${{{{ inputs.{input_name}", run_script)

        self.assertIn("COUNTRY_SEARCHED: ${{ inputs.country_searched }}", workflow)
        self.assertIn("RESEARCH_MODE: ${{ inputs.mode }}", workflow)
        self.assertIn("SOURCE_LIMIT: ${{ inputs.max_sources_per_industry }}", workflow)


if __name__ == "__main__":
    unittest.main()
