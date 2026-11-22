"""Offline demo data loader for the Global Workforce Intelligence dashboard."""
import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HISTORY_PATH = ROOT / "data" / "findings_history.jsonl"


def _observation_weeks(value, fallback_dates=None):
    """Return distinct ISO Monday dates for internal trend calculations."""
    if value is None:
        values = []
    elif isinstance(value, str):
        values = [part.strip() for part in value.split(",") if part.strip()]
    elif isinstance(value, (list, tuple, set)):
        values = [str(part).strip() for part in value if str(part).strip()]
    else:
        values = [str(value).strip()]

    weeks = set()
    for item in values:
        try:
            day = date.fromisoformat(str(item)[:10])
            weeks.add((day - timedelta(days=day.weekday())).isoformat())
        except (TypeError, ValueError):
            continue
    if not weeks:
        for item in fallback_dates or []:
            if not item:
                continue
            try:
                day = date.fromisoformat(str(item)[:10])
                weeks.add((day - timedelta(days=day.weekday())).isoformat())
            except (TypeError, ValueError):
                continue
    return sorted(weeks)

def load_demo_findings(path=HISTORY_PATH):
    """Load committed research history as a read-only demo snapshot."""
    records = []
    path = Path(path)
    if not path.exists():
        return records
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(item, dict):
                continue
            weeks = _observation_weeks(
                item.get("weeks_seen"),
                fallback_dates=[item.get("first_seen_week"), item.get("last_seen_week"), item.get("first_seen"), item.get("last_seen")],
            )
            records.append({
                "Industry": item.get("industry") or "Uncategorized",
                "Identified Problem": item.get("problem_type") or "Unclassified",
                "Problem Description": item.get("description") or "",
                "Country": item.get("country") or "Not specified",
                "Region": item.get("region") or "Not specified",
                "Source Name": item.get("source_name") or "",
                "Source URL": item.get("source_url") or "",
                "Source Platform": item.get("source_platform") or "Web",
                "First Seen": item.get("first_seen") or "",
                "Last Seen": item.get("last_seen") or "",
                "Observation Weeks": ", ".join(weeks),
                "Weeks Seen": len(weeks),
                "Occurrences": item.get("occurrences") or 1,
            })
    return records
