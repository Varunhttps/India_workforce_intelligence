"""Evidence-based weekly workforce signal and opportunity comparisons."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta


def monday_week(value: str) -> str:
    """Return the ISO Monday date for an ISO YYYY-MM-DD date."""
    day = date.fromisoformat(str(value)[:10])
    return (day - timedelta(days=day.weekday())).isoformat()


def _week(value):
    if not value:
        return None
    try:
        return monday_week(str(value))
    except (TypeError, ValueError):
        return None


def _weeks_for(record):
    weeks = set()
    for value in record.get("weeks_seen") or []:
        parsed = _week(value)
        if parsed:
            weeks.add(parsed)
    for key in ("first_seen_week", "last_seen_week", "first_seen", "last_seen"):
        parsed = _week(record.get(key))
        if parsed:
            weeks.add(parsed)
    return weeks


def _normalized(value):
    return " ".join(str(value or "").casefold().split())


def _date_bounds(group, record):
    for key in ("first_seen", "last_seen"):
        value = record.get(key)
        if not value:
            continue
        current = group.get(key)
        if key == "first_seen":
            if current is None or str(value) < current:
                group[key] = str(value)
        elif current is None or str(value) > current:
            group[key] = str(value)


def _base_group(industry, label):
    return {
        "industry": industry,
        "label": label,
        "sources": set(),
        "countries": set(),
        "weeks": set(),
        "sources_by_week": defaultdict(set),
        "countries_by_week": defaultdict(set),
        "records_by_week": defaultdict(set),
        "first_seen": None,
        "last_seen": None,
    }


def _record_key(record):
    return str(record.get("finding_key") or "|".join(str(record.get(key) or "") for key in
        ("problem_type", "description", "country", "industry", "source_url")))


def _collect(group, record, weeks):
    source = str(record.get("source_url") or "").strip()
    country = str(record.get("country") or "").strip()
    if source:
        group["sources"].add(source)
    if country:
        group["countries"].add(country)
    group["weeks"].update(weeks)
    _date_bounds(group, record)
    key = _record_key(record)
    for week in weeks:
        group["records_by_week"][week].add(key)
        if source:
            group["sources_by_week"][week].add(source)
        if country:
            group["countries_by_week"][week].add(country)


def _counts(group, current_week, previous_week):
    current_sources = group["sources_by_week"].get(current_week, set())
    previous_sources = group["sources_by_week"].get(previous_week, set())
    current_countries = group["countries_by_week"].get(current_week, set())
    previous_countries = group["countries_by_week"].get(previous_week, set())
    return {
        "current_sources": current_sources,
        "previous_sources": previous_sources,
        "current_countries": current_countries,
        "previous_countries": previous_countries,
        "source_delta": len(current_sources) - len(previous_sources),
        "country_delta": len(current_countries) - len(previous_countries),
    }


def analyze_weekly_trends(history_records, current_week=None):
    """Aggregate problems by industry/category and compare evidence with last week.

    Growing evidence is a research signal, not proof that a real-world problem
    is worsening. Missing current-week observations never imply resolution.
    """
    current_week = _week(current_week) or monday_week(date.today().isoformat())
    previous_week = (date.fromisoformat(current_week) - timedelta(days=7)).isoformat()
    groups = {}
    for record in history_records or []:
        industry = str(record.get("industry") or "Unclassified").strip()
        problem = str(record.get("problem_type") or "Unclassified").strip()
        key = (_normalized(industry), _normalized(problem))
        group = groups.setdefault(key, _base_group(industry, problem))
        _collect(group, record, _weeks_for(record))

    output = []
    for group in groups.values():
        counts = _counts(group, current_week, previous_week)
        current_sources = counts["current_sources"]
        previous_sources = counts["previous_sources"]
        current_countries = counts["current_countries"]
        previous_countries = counts["previous_countries"]
        source_delta = counts["source_delta"]
        country_delta = counts["country_delta"]
        observed_now = current_week in group["weeks"]
        first_week = min(group["weeks"]) if group["weeks"] else ""
        is_new = observed_now and first_week == current_week
        worsening = observed_now and len(previous_sources) > 0 and (
            source_delta >= 2 or (source_delta > 0 and country_delta > 0)
        )
        emerging = observed_now and len(group["weeks"]) <= 3 and (
            len(current_sources) >= 2 or len(current_countries) >= 2
        )
        if not observed_now:
            momentum = "Not observed this week"
        elif is_new:
            momentum = "New evidence"
        elif worsening:
            momentum = "Potentially worsening — evidence expansion"
        elif emerging:
            momentum = "Emerging"
        elif source_delta > 0 and country_delta > 0:
            momentum = "Evidence and geographic coverage growing"
        elif source_delta > 0:
            momentum = "Source coverage growing"
        elif country_delta > 0:
            momentum = "Geographic coverage growing"
        elif source_delta < 0 or country_delta < 0:
            momentum = "Evidence receding"
        else:
            momentum = "Stable evidence"
        weeks = sorted(group["weeks"])
        output.append({
            "industry": group["industry"],
            "problem_type": group["label"],
            "signal_status": "New this week" if is_new else ("Active this week" if observed_now else "Not observed this week"),
            "signal_momentum": momentum,
            "emerging_signal": emerging,
            "worsening_signal": worsening,
            "weeks_observed": len(group["weeks"]),
            "countries": sorted(group["countries"]),
            "country_count": len(group["countries"]),
            "supporting_sources": sorted(group["sources"]),
            "source_count": len(group["sources"]),
            "current_week_source_count": len(current_sources),
            "previous_week_source_count": len(previous_sources),
            "source_count_delta": source_delta,
            "current_week_country_count": len(current_countries),
            "previous_week_country_count": len(previous_countries),
            "country_count_delta": country_delta,
            "first_seen": group["first_seen"] or "",
            "last_seen": group["last_seen"] or "",
            "latest_week": weeks[-1] if weeks else "",
            "current_week": current_week,
            "previous_week": previous_week,
        })
    output.sort(key=lambda row: (row["industry"].casefold(), row["problem_type"].casefold()))
    return output


def analyze_opportunity_changes(history_records, current_week=None, classifier=None):
    """Compare mapped planning capabilities week over week using source/country breadth."""
    if classifier is None:
        return []
    current_week = _week(current_week) or monday_week(date.today().isoformat())
    previous_week = (date.fromisoformat(current_week) - timedelta(days=7)).isoformat()
    groups = {}
    for record in history_records or []:
        mapped = classifier(record, supporting_source_count=1)
        if not mapped:
            continue
        industry = str(record.get("industry") or "Unclassified").strip()
        capability = str(mapped.get("capability") or mapped.get("market_need") or "Unclassified").strip()
        key = (_normalized(industry), _normalized(capability))
        group = groups.setdefault(key, {
            **_base_group(industry, capability),
            "market_need": mapped.get("market_need", ""),
            "capability": capability,
            "features": set(),
            "business_values": set(),
            "priorities": set(),
            "representative": record,
        })
        if mapped.get("feature"):
            group["features"].add(str(mapped["feature"]))
        if mapped.get("business_value"):
            group["business_values"].add(str(mapped["business_value"]))
        if mapped.get("priority"):
            group["priorities"].add(str(mapped["priority"]))
        _collect(group, record, _weeks_for(record))

    priority_order = {"low": 1, "medium": 2, "high": 3}
    output = []
    for group in groups.values():
        counts = _counts(group, current_week, previous_week)
        current_sources, previous_sources = counts["current_sources"], counts["previous_sources"]
        current_countries, previous_countries = counts["current_countries"], counts["previous_countries"]
        source_delta, country_delta = counts["source_delta"], counts["country_delta"]
        observed_now = current_week in group["weeks"]
        first_week = min(group["weeks"]) if group["weeks"] else ""
        if not observed_now:
            change = "Not observed this week"
        elif first_week == current_week:
            change = "New this week"
        elif source_delta > 0 or country_delta > 0:
            change = "Expanded evidence"
        elif source_delta < 0 or country_delta < 0:
            change = "Evidence receded"
        else:
            change = "Stable evidence"
        classifier_result = classifier(group["representative"], supporting_source_count=len(group["sources"])) or {}
        priorities = group["priorities"] | ({str(classifier_result["priority"])} if classifier_result.get("priority") else set())
        priority = max(priorities, key=lambda value: priority_order.get(value.casefold(), 0)) if priorities else ""
        weeks = sorted(group["weeks"])
        output.append({
            "industry": group["industry"],
            "market_need": group["market_need"],
            "capability": group["capability"],
            "feature": "; ".join(sorted(group["features"])),
            "business_value": "; ".join(sorted(group["business_values"])),
            "priority": priority,
            "change_status": change,
            "new_this_week": observed_now and first_week == current_week,
            "expanded_evidence": observed_now and change == "Expanded evidence",
            "supporting_sources": sorted(group["sources"]),
            "source_count": len(group["sources"]),
            "current_week_source_count": len(current_sources),
            "previous_week_source_count": len(previous_sources),
            "source_count_delta": source_delta,
            "countries": sorted(group["countries"]),
            "country_count": len(group["countries"]),
            "current_week_country_count": len(current_countries),
            "previous_week_country_count": len(previous_countries),
            "country_count_delta": country_delta,
            "weeks_observed": len(group["weeks"]),
            "first_seen": group["first_seen"] or "",
            "last_seen": group["last_seen"] or "",
            "latest_week": weeks[-1] if weeks else "",
            "current_week": current_week,
            "previous_week": previous_week,
        })
    output.sort(key=lambda row: (row["industry"].casefold(), row["capability"].casefold()))
    return output
