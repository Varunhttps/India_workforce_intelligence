"""Read-only health and freshness summary for the weekly workforce research workflow."""
from __future__ import annotations

from datetime import date, datetime, timezone

import requests

WORKFLOW_RUNS_URL = (
    "https://api.github.com/repos/Varunhttps/India_workforce_intelligence"
    "/actions/workflows/weekly-research.yml/runs"
)
FRESHNESS_DAYS = 8
API_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def _parse_timestamp(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _now_utc(now=None):
    if now is None:
        return datetime.now(timezone.utc)
    if isinstance(now, datetime):
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return now.astimezone(timezone.utc)
    if isinstance(now, date):
        return datetime.combine(now, datetime.min.time(), tzinfo=timezone.utc)
    raise TypeError("now must be a date or datetime")


def _run_label(run):
    status = str(run.get("status") or "").casefold()
    conclusion = str(run.get("conclusion") or "").casefold()
    if status == "completed":
        return conclusion.replace("_", " ").title() if conclusion else "Completed"
    if status in {"queued", "waiting", "requested"}:
        return "Queued"
    if status in {"in_progress", "pending"}:
        return "Running"
    return status.title() or "Unknown"


def _run_summary(run):
    timestamp = _parse_timestamp(
        run.get("updated_at") or run.get("created_at") or run.get("run_started_at")
    )
    return {
        "status": str(run.get("status") or "unknown").casefold(),
        "conclusion": str(run.get("conclusion") or "").casefold(),
        "label": _run_label(run),
        "run_number": run.get("run_number"),
        "date": timestamp.strftime("%Y-%m-%d") if timestamp else "",
        "timestamp": timestamp.isoformat() if timestamp else "",
        "url": str(run.get("html_url") or ""),
    }


def summarize_workflow_runs(payload, now=None):
    """Summarize the latest run and latest successful run from an API payload."""
    runs = payload.get("workflow_runs") if isinstance(payload, dict) else None
    if not isinstance(runs, list):
        return {"available": False, "error": "GitHub Actions returned an unexpected response."}

    valid_runs = [run for run in runs if isinstance(run, dict)]
    valid_runs.sort(
        key=lambda run: (
            _parse_timestamp(run.get("created_at") or run.get("updated_at"))
            or datetime.min.replace(tzinfo=timezone.utc)
        ),
        reverse=True,
    )
    latest_run = _run_summary(valid_runs[0]) if valid_runs else None
    successes = [
        run for run in valid_runs
        if str(run.get("status") or "").casefold() == "completed"
        and str(run.get("conclusion") or "").casefold() == "success"
    ]
    latest_success = _run_summary(successes[0]) if successes else None

    age_days = None
    freshness = "Unknown"
    if latest_success and latest_success["timestamp"]:
        successful_at = _parse_timestamp(latest_success["timestamp"])
        age_days = max(0, int((_now_utc(now) - successful_at).total_seconds() // 86400))
        freshness = "Fresh" if age_days <= FRESHNESS_DAYS else "Stale"
        latest_success["age_days"] = age_days
    elif latest_success:
        latest_success["age_days"] = None

    return {
        "available": True,
        "latest_run": latest_run,
        "latest_success": latest_success,
        "freshness": freshness,
        "freshness_days": FRESHNESS_DAYS,
    }


def fetch_latest_research_run_health(now=None):
    """Fetch public workflow status; gracefully handle API/rate-limit failures."""
    try:
        response = requests.get(
            WORKFLOW_RUNS_URL,
            params={"branch": "main", "per_page": 20},
            headers=API_HEADERS,
            timeout=8,
        )
        response.raise_for_status()
        return summarize_workflow_runs(response.json(), now=now)
    except (requests.RequestException, ValueError):
        return {
            "available": False,
            "error": "GitHub Actions run status is temporarily unavailable.",
        }
