"""Offline demo data loader for the Global Workforce Intelligence dashboard."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HISTORY_PATH = ROOT / "data" / "findings_history.jsonl"


def _format_weeks(value):
    """Handle the list and comma-separated string forms of observation weeks."""
    if value is None:
        return ""
    if isinstance(value, str):
        return ", ".join(part.strip() for part in value.split(",") if part.strip())
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(part).strip() for part in value if str(part).strip())
    return str(value)


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
                "Weeks Seen": _format_weeks(item.get("weeks_seen")),
                "Occurrences": item.get("occurrences") or 1,
            })
    return records
