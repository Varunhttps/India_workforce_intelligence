"""Week-over-week workforce problem signals from the cumulative finding history."""
from __future__ import annotations

from datetime import date, timedelta


def monday_week(value: str) -> str:
    day = date.fromisoformat(str(value)[:10])
    return (day - timedelta(days=day.weekday())).isoformat()


def analyze_weekly_trends(history_records, current_week=None):
    """Aggregate evidence by industry/problem, avoiding source-level duplicates.

    Signals are evidence-based statuses only: newly observed, active this week,
    or not observed in the latest week. Absence is not interpreted as resolution.
    """
    current_week = current_week or monday_week(date.today().isoformat())
    groups = {}
    for record in history_records or []:
        industry = str(record.get("industry") or "Unclassified").strip()
        problem = str(record.get("problem_type") or "Unclassified").strip()
        key = (industry.casefold(), problem.casefold())
        group = groups.setdefault(key, {
            "industry": industry,
            "problem": problem,
            "countries": set(),
            "sources": set(),
            "weeks": set(),
            "first_seen": None,
            "last_seen": None,
        })
        country = record.get("country")
        source = record.get("source_url")
        if country:
            group["countries"].add(str(country))
        if source:
            group["sources"].add(str(source))
        weeks = record.get("weeks_seen") or []
        for week in weeks:
            try:
                group["weeks"].add(monday_week(str(week)))
            except ValueError:
                continue
        first = record.get("first_seen_week")
        last = record.get("last_seen_week")
        if not first and record.get("first_seen"):
            try:
                first = monday_week(str(record["first_seen"]))
            except ValueError:
                first = None
        if not last and record.get("last_seen"):
            try:
                last = monday_week(str(record["last_seen"]))
            except ValueError:
                last = None
        if first:
            group["weeks"].add(first)
        if last:
            group["weeks"].add(last)
        for candidate in (record.get("first_seen"), record.get("last_seen")):
            if candidate and (group["first_seen"] is None or str(candidate) < group["first_seen"]):
                group["first_seen"] = str(candidate)
            if candidate and (group["last_seen"] is None or str(candidate) > group["last_seen"]):
                group["last_seen"] = str(candidate)

    output = []
    for group in groups.values():
        weeks = sorted(group["weeks"])
        seen_this_week = current_week in group["weeks"] or group["last_seen"] and monday_week(group["last_seen"]) == current_week
        if seen_this_week and group["first_seen"] and monday_week(group["first_seen"]) == current_week:
            status = "New this week"
        elif seen_this_week:
            status = "Active this week"
        else:
            status = "Not observed this week"
        output.append({
            "industry": group["industry"],
            "problem_type": group["problem"],
            "signal_status": status,
            "weeks_observed": len(group["weeks"]),
            "countries": sorted(group["countries"]),
            "country_count": len(group["countries"]),
            "supporting_sources": sorted(group["sources"]),
            "source_count": len(group["sources"]),
            "first_seen": group["first_seen"] or "",
            "last_seen": group["last_seen"] or "",
            "latest_week": weeks[-1] if weeks else "",
            "current_week": current_week,
        })
    output.sort(key=lambda row: (row["industry"].casefold(), row["problem_type"].casefold()))
    return output
