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
        self.assertRegex(tests_job, r"(?m)^    permissions:\\s*\\n      contents:\\s*read\\s*$")
        self.assertRegex(tests_job, r"(?m)^          persist-credentials:\\s*false\\s*$")

    def test_research_job_is_gated_by_tests_and_write_permission_is_scoped(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        research_job = _job_block(workflow, "weekly-research")
        self.assertTrue(research_job, "weekly-research job is missing")
        self.assertRegex(research_job, r"(?m)^    needs:\\s*tests\\s*$")
        self.assertRegex(research_job, r"(?m)^    permissions:\\s*\\n      contents:\\s*write\\s*$")
        self.assertEqual(
            len(re.findall(r"(?m)^\\s*contents:\\s*write\\s*$", workflow)),
            1,
            "contents: write must be granted only to the publishing research job",
        )

    def test_research_job_does_not_persist_write_token_and_push_auth_is_late_scoped(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        research_job = _job_block(workflow, "weekly-research")
        checkout = re.search(
            r"(?ms)^      - uses: actions/checkout@v7\\s*\\n        with:\\s*\\n          ref: main\\s*\\n          persist-credentials: false\\s*$",
            research_job,
        )
        self.assertIsNotNone(checkout, "research checkout must not persist write credentials")

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
        self.assertIsNone(
            re.search(r"(?m)^permissions:\\s*$", workflow),
            "write permission must not be granted at workflow scope",
        )


if __name__ == "__main__":
    unittest.main()