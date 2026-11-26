import re
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "weekly-research.yml"


def _job_block(workflow, job_name):
    header = re.search(rf"(?m)^  {re.escape(job_name)}:\s*$", workflow)
    if header is None:
        return ""
    start = header.end()
    next_job = re.search(r"(?m)^  [A-Za-z0-9_-]+:\s*$", workflow[start:])
    end = start + next_job.start() if next_job else len(workflow)
    return workflow[start:end]


class WeeklyWorkflowSafetyTests(unittest.TestCase):
    def test_tests_job_is_read_only_and_does_not_persist_checkout_credentials(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        tests_job = _job_block(workflow, "tests")
        self.assertTrue(tests_job, "weekly-research workflow must include a tests job")
        self.assertIn("    if: github.ref == 'refs/heads/main'", tests_job,
                      "preflight job must not run from non-main manual dispatches")
        self.assertIn("    permissions:", tests_job)
        self.assertIn("      contents: read", tests_job)
        self.assertIn("          persist-credentials: false", tests_job)
        checkout_block = tests_job.split("      - uses: actions/checkout@v7", 1)[1].split(
            "      - uses: actions/setup-python@v7", 1
        )[0]
        self.assertIn("          ref: main", checkout_block,
                      "preflight tests must test the same main branch that research checks out")

    def test_research_job_is_gated_by_tests_and_write_permission_is_scoped(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        research_job = _job_block(workflow, "weekly-research")
        self.assertTrue(research_job, "weekly-research job is missing")
        self.assertIn("    if: github.ref == 'refs/heads/main'", research_job,
                      "research job must be limited to main")
        self.assertIn("    needs: tests", research_job)
        self.assertIn("    permissions:", research_job)
        self.assertIn("      contents: write", research_job)
        self.assertEqual(workflow.count("      contents: write"), 1,
                         "contents: write must be granted only to the publishing research job")

    def test_research_job_does_not_persist_write_token_and_push_auth_is_late_scoped(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        research_job = _job_block(workflow, "weekly-research")
        checkout_block = research_job.split("      - uses: actions/checkout@v7", 1)[1].split(
            "      - uses: actions/setup-python@v7", 1
        )[0]
        self.assertIn("ref: main", checkout_block)
        self.assertIn("persist-credentials: false", checkout_block,
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

    def test_ci_workflow_is_read_only_and_does_not_persist_checkout_credentials(self):
        workflow_path = ROOT / ".github" / "workflows" / "tests.yml"
        workflow = workflow_path.read_text(encoding="utf-8")
        header = workflow.split("jobs:", 1)[0]
        self.assertIn("permissions:", header)
        self.assertIn("contents: read", header)
        self.assertNotIn("contents: write", workflow)
        tests_job = _job_block(workflow, "tests")
        self.assertTrue(tests_job, "CI workflow must include a tests job")
        checkout_block = tests_job.split("      - uses: actions/checkout@v7", 1)[1].split(
            "      - uses: actions/setup-python@v7", 1
        )[0]
        self.assertIn("persist-credentials: false", checkout_block)

    def test_workflow_has_no_top_level_write_permission(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        header = workflow.split("jobs:", 1)[0]
        self.assertNotIn("permissions:", header)


if __name__ == "__main__":
    unittest.main()
