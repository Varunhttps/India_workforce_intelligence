"""Evidence-count momentum comparisons for workforce problems.

Counts are publication/discovery signals, not measures of actual problem severity.
"""
from __future__ import annotations

from datetime import date, timedelta


def _week(value):
    day = date.fromisoformat(str(value)[:10])
    return (day - timedelta(days=day.weekday())).isoformat()


def _week_list(record):
    weeks = record.get("weeks_seen") or []
    normalized = set()
    for value in weeks:
        try:
            normalized.add(_week(value))
        except (ValueError, TypeError):
            continue
    for field in ("first_seen_week", "last_seen_week"):
        value = record.get(field)
        if value:
            try:
                normalized.add(_week(value))
            except (ValueError, TypeError):
                pass
    if not normalized:
        for field in ("first_seen", "last_seen"):
            value = record.get(field)
            if value:
                try:
                    normalized.add(_week(value))
                except (ValueError, TypeError):
                    pass
    return normalized


def analyze_signal_momentum(history_records, current_week=None):
    """Compare distinct supporting sources in the current and prior ISO week.

    One source/finding record contributes at most once per problem per week.
    Weeks missing from history are zero-count weeks, but interpreted cautiously.
    """
    current_week = _week(current_week or date.today().isoformat())
    prior_week = (date.fromisoformat(current_week) - timedelta(days=7)).isoformat()
    buckets = {}
    for record in history_records or []:
        industry = str(record.get("industry") or "Unclassified").strip()
        problem = str(record.get("problem_type") or "Unclassified").strip()
        key = (industry.casefold(), problem.casefold())
        bucket = buckets.setdefault(key, {
            "industry": industry, "problem_type": problem,
            "current_sources": set(), "previous_sources": set(),
            "countries": set(), "first_seen": None, "last_seen": None,
        })
        source = record.get("source_url") or record.get("finding_key") or record.get("source_name")
        weeks = _week_list(record)
        if source and current_week in weeks:
            bucket["current_sources"].add(str(source))
        if source and prior_week in weeks:
            bucket["previous_sources"].add(str(source))
        if record.get("country"):
            bucket["countries"].add(str(record["country"]))
        for field in ("first_seen", "last_seen"):
            value = record.get(field)
            if value:
                if bucket["first_seen"] is None or str(value) < bucket["first_seen"]:
                    bucket["first_seen"] = str(value)
                if bucket["last_seen"] is None or str(value) > bucket["last_seen"]:
                    bucket["last_seen"] = str(value)

    results = []
    for bucket in buckets.values():
        now = len(bucket["current_sources"])
        before = len(bucket["previous_sources"])
        delta = now - before
        if now == before:
            trend = "Stable"
        elif now > before:
            trend = "Increasing evidence"
        else:
            trend = "Decreasing evidence"
        combined_text = bucket["problem_type"].casefold()
        staffing_terms = ("shortage", "vacanc", "hiring", "recruit", "attraction", "retention", "attrition", "labor", "labour")
        planning_terms = ("forecast", "planning", "capacity", "allocation", "mismatch", "skills", "upskill", "productivity", "cost", "workforce transformation")
        staffing = any(term in combined_text for term in staffing_terms)
        planning = any(term in combined_text for term in planning_terms)
        results.append({
            "industry": bucket["industry"],
            "problem_type": bucket["problem_type"],
            "current_week": current_week,
            "previous_week": prior_week,
            "current_source_count": now,
            "previous_source_count": before,
            "source_delta": delta,
            "trend": trend,
            "countries": sorted(bucket["countries"]),
            "country_count": len(bucket["countries"]),
            "first_seen": bucket["first_seen"] or "",
            "last_seen": bucket["last_seen"] or "",
            "staffing_opportunity_signal": "Candidate" if staffing else "Review",
            "nexplan_planning_signal": "Candidate" if planning else "Review",
            "interpretation_note": "Evidence/source counts can change with coverage and publishing activity; they do not prove workforce problem severity changed.",
        })
    results.sort(key=lambda row: (-row["current_source_count"], -row["source_delta"], row["industry"].casefold(), row["problem_type"].casefold()))
    return results


def rank_emerging_industries(momentum_rows):
    """Rank industries by current distinct supporting sources and problem diversity."""
    aggregated = {}
    for row in momentum_rows or []:
        industry = row["industry"]
        item = aggregated.setdefault(industry, {"industry": industry, "current_sources": 0, "problems": set(), "increasing_problems": 0, "staffing_candidates": 0, "planning_candidates": 0})
        item["current_sources"] += int(row.get("current_source_count") or 0)
        item["problems"].add(row["problem_type"])
        item["increasing_problems"] += row.get("trend") == "Increasing evidence"
        item["staffing_candidates"] += row.get("staffing_opportunity_signal") == "Candidate"
        item["planning_candidates"] += row.get("nexplan_planning_signal") == "Candidate"
    ranked = []
    for item in aggregated.values():
        ranked.append({**item, "distinct_problem_count": len(item["problems"]), "problems": sorted(item["problems"])})
        del ranked[-1]["problems"]
    ranked.sort(key=lambda item: (-item["current_sources"], -item["distinct_problem_count"], -item["increasing_problems"], item["industry"].casefold()))
    for index, item in enumerate(ranked, 1):
        item["rank"] = index
    return ranked
