"""Offline demo data loader for the Global Workforce Intelligence dashboard."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HISTORY_PATH = ROOT / "data" / "findings_history.jsonl"


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
            records.append({
                "Industry": item.get("industry", "Uncategorized"),
                "Identified Problem": item.get("problem_type", "Unclassified"),
                "Problem Description": item.get("description", ""),
                "Country": item.get("country") or "Not specified",
                "Region": item.get("region") or "Not specified",
                "Source Name": item.get("source_name", ""),
                "Source URL": item.get("source_url", ""),
                "Source Platform": item.get("source_platform", "Web"),
                "First Seen": item.get("first_seen", ""),
                "Last Seen": item.get("last_seen", ""),
                "Weeks Seen": ", ".join(item.get("weeks_seen", []) or []),
                "Occurrences": item.get("occurrences", 1),
            })
    return records
