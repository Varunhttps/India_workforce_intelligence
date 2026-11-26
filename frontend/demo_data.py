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


def build_emerging_challenge_chart_data(records, top_n=10):
    """Return ranked challenge counts and a truthful trend caption from dated observations."""
    from collections import Counter, defaultdict

    overall_counts = Counter()
    monthly_counts = defaultdict(Counter)
    for record in records or []:
        if not isinstance(record, dict):
            continue
        problem = str(record.get("Identified Problem") or "Unclassified").strip() or "Unclassified"
        overall_counts[problem] += 1
        weeks = _observation_weeks(record.get("Observation Weeks"))
        if not weeks:
            fallback_date = record.get("Last Seen") or record.get("First Seen")
            weeks = _observation_weeks(None, fallback_dates=[fallback_date])
        for week in weeks:
            monthly_counts[week[:7]][problem] += 1

    months = sorted(monthly_counts)
    has_comparison = False
    if len(months) >= 4:
        recent = Counter()
        prior = Counter()
        for month in months[-2:]:
            recent.update(monthly_counts[month])
        for month in months[-4:-2]:
            prior.update(monthly_counts[month])
        changes = {problem: recent.get(problem, 0) - prior.get(problem, 0)
                   for problem in set(recent) | set(prior)}
        has_comparison = True
        period = "increase across the latest two months versus the preceding two months"
    elif len(months) >= 2:
        recent = monthly_counts[months[-1]]
        prior = monthly_counts[months[-2]]
        changes = {problem: recent.get(problem, 0) - prior.get(problem, 0)
                   for problem in set(recent) | set(prior)}
        has_comparison = True
        period = "increase in the latest month versus the previous month"
    elif months:
        recent = monthly_counts[months[-1]]
        changes = {}
        period = "only one month of observations; ranked by counts (no trend inferred)"
    else:
        recent = overall_counts
        changes = {}
        period = "no observation dates available; ranked by overall counts"

    if has_comparison:
        increasing = [problem for problem, delta in changes.items() if delta > 0]
        if increasing:
            increasing.sort(key=lambda problem: (-changes[problem], -recent.get(problem, 0), problem.lower()))
            chosen = increasing[:max(1, int(top_n))]
            caption = "Ranked by " + period
        else:
            chosen = sorted(recent, key=lambda problem: (-recent[problem], problem.lower()))[:max(1, int(top_n))]
            caption = "No challenges increased in the comparison period; ranked by recent counts"
    else:
        chosen = sorted(recent, key=lambda problem: (-recent[problem], problem.lower()))[:max(1, int(top_n))]
        caption = period

    rows = []
    for problem in chosen:
        count = int(recent.get(problem, 0))
        delta = int(changes[problem]) if has_comparison else None
        label = f"{count} (Δ {delta:+d})" if delta is not None else str(count)
        rows.append({
            "Challenge": problem,
            "Recent findings": count,
            "Change": delta,
            "Label": label,
        })
    rows.sort(key=lambda row: (-row["Recent findings"], row["Challenge"].lower()))
    return rows, caption
