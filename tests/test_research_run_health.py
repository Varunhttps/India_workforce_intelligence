import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import requests

from workforce_intelligence.research_run_health import (
    FRESHNESS_DAYS,
    fetch_latest_research_run_health,
    summarize_workflow_runs,
)


class ResearchRunHealthTests(unittest.TestCase):
    NOW = datetime(2026, 11, 23, 12, tzinfo=timezone.utc)

    def test_latest_success_is_fresh(self):
        result = summarize_workflow_runs(
            {"workflow_runs": [{
                "status": "completed", "conclusion": "success",
                "created_at": "2026-11-23T04:00:00Z",
                "updated_at": "2026-11-23T04:05:00Z",
                "html_url": "https://github.com/example/run/1", "run_number": 31,
            }]},
            now=self.NOW,
        )
        self.assertTrue(result["available"])
        self.assertEqual(result["latest_run"]["label"], "Success")
        self.assertEqual(result["latest_success"]["age_days"], 0)
        self.assertEqual(result["freshness"], "Fresh")

    def test_latest_failed_run_does_not_hide_recent_success(self):
        result = summarize_workflow_runs(
            {"workflow_runs": [
                {"status": "completed", "conclusion": "failure",
                 "created_at": "2026-11-23T11:00:00Z", "updated_at": "2026-11-23T11:05:00Z"},
                {"status": "completed", "conclusion": "success",
                 "created_at": "2026-11-22T06:00:00Z", "updated_at": "2026-11-22T06:05:00Z"},
            ]},
            now=self.NOW,
        )
        self.assertEqual(result["latest_run"]["label"], "Failure")
        self.assertEqual(result["latest_success"]["date"], "2026-11-22")
        self.assertEqual(result["freshness"], "Fresh")

    def test_stale_success_is_detected_after_grace_window(self):
        result = summarize_workflow_runs(
            {"workflow_runs": [{
                "status": "completed", "conclusion": "success",
                "created_at": "2026-11-10T06:00:00Z",
                "updated_at": "2026-11-10T06:05:00Z",
            }]},
            now=self.NOW,
        )
        self.assertEqual(result["latest_success"]["age_days"], 13)
        self.assertEqual(result["freshness"], "Stale")
        self.assertEqual(result["freshness_days"], FRESHNESS_DAYS)

    def test_no_success_is_unknown_not_stale(self):
        result = summarize_workflow_runs(
            {"workflow_runs": [
                {"status": "in_progress", "conclusion": None, "created_at": "2026-11-23T11:00:00Z"},
                {"status": "completed", "conclusion": "cancelled", "created_at": "2026-11-22T06:00:00Z"},
            ]},
            now=self.NOW,
        )
        self.assertEqual(result["latest_run"]["label"], "Running")
        self.assertIsNone(result["latest_success"])
        self.assertEqual(result["freshness"], "Unknown")

    def test_malformed_payload_is_unavailable(self):
        result = summarize_workflow_runs({"workflow_runs": "not-a-list"}, now=self.NOW)
        self.assertFalse(result["available"])
        self.assertIn("error", result)

    @patch("workforce_intelligence.research_run_health.requests.get")
    def test_api_failure_returns_safe_fallback(self, get):
        get.side_effect = requests.Timeout()
        result = fetch_latest_research_run_health(now=self.NOW)
        self.assertFalse(result["available"])
        self.assertIn("temporarily unavailable", result["error"])

    @patch("workforce_intelligence.research_run_health.requests.get")
    def test_fetch_uses_public_workflow_endpoint_and_timeout(self, get):
        response = Mock()
        response.json.return_value = {"workflow_runs": [{
            "status": "completed", "conclusion": "success",
            "created_at": "2026-11-23T06:00:00Z",
            "updated_at": "2026-11-23T06:05:00Z",
        }]}
        get.return_value = response
        result = fetch_latest_research_run_health(now=self.NOW)
        get.assert_called_once()
        self.assertEqual(get.call_args.kwargs["params"]["branch"], "main")
        self.assertEqual(get.call_args.kwargs["timeout"], 8)
        self.assertEqual(result["freshness"], "Fresh")


if __name__ == "__main__":
    unittest.main()
