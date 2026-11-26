import re
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "weekly-research.yml"


def _job_block(workflow, job_name):
    header = re.search(rf"(?m)^  {re.escape(job_name)}:\\s*$", workflow)
    if header is None:
        return ""
    start = header.end()
    next_job = re.search(r"(?m)^  [A-Za-z0-9_-]+:\\s*$", workflow[start:])
    end = start + next_job.start() if next_job else len(workflow)
    return workflow[start:end]


class WeeklyWorkflowSafetyTests(unittest.TestCase):
    def test_tests_job_is_read_only_and_does_not_persist_checkout_credentials(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        tests_job = _job_block(workflow, "tests")
        self.assertTrue(tests_job, "weekly-research workflow must include a tests job")
        self.assertIn("    permissions:\\n      contents: read", tests_job)
        self.assertIn("          persist-credentials: false", tests_job)

    def test_research_job_is_gated_by_tests_and_write_permission_is_scoped(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        research_job = _job_block(workflow, "weekly-research")
        self.assertTrue(research_job, "weekly-research job is missing")
        self.assertIn("    needs: tests", research_job)
        self.assertIn("    permissions:\\n      contents: write", research_job)
        self.assertEqual(workflow.count("      contents: write"), 1,
                         "contents: write must be granted only to the publishing research job")

    def test_research_job_does_not_persist_write_token_and_push_auth_is_late_scoped(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        research_job = _job_block(workflow, "weekly-research")
        checkout_block = research_job.split("      - uses: actions/checkout@v7", 1)[1].split(
            "      - uses: actions/setup-python@v7", 1
        )[0]
        self.assertIn("          ref: main\\n          persist-credentials: false", checkout_block,
                      "research checkout must not persist write credentials")

        research_step = research_job.split(
            "      - name: Run research and update the persistent Google Sheet", 1
        )[1].split("      - name: Commit updated public-source research history", 1)[0]
        self.assertNotIn("GH_TOKEN", research_step, "write token must not be available during research")

        push_step = research_job.split(
            "      - name: Commit updated public-source research history", 1
        )[1]
        self.assertIn("GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}", push_step)
        self.assertIn('git -c credential.helper="$credential_helper" push origin HEAD:main', push_step)
        self.assertIn("credential_helper", push_step)
        self.assertIn("rm -f", push_step)

    def test_workflow_has_no_top_level_write_permission(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertNotIn("\\npermissions:\\n  contents: write\\n", workflow)


if __name__ == "__main__":
    unittest.main()