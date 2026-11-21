"""Transparent manager-facing prioritization of mapped workforce opportunities."""
from __future__ import annotations

from datetime import date, datetime


SCORING_WEIGHTS = {
    "signal_frequency": 25,
    "recency": 20,
    "business_impact": 25,
    "evidence_strength": 20,
    "actionability": 10,
}


def _norm(value):
    return " ".join(str(value or "").casefold().split())


def _date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _truthy_text(value):
    text = str(value or "").strip()
    return text if text.casefold() not in {"nan", "none", "null"} else ""


def classify_track(market_need="", capability="", feature=""):
    text = _norm(f"{market_need} {capability} {feature}")
    staffing_terms = (
        "recruit", "recruitment", "hiring", "vacancy", "talent acquisition",
        "hard-to-fill", "time-to-fill", "staffing service", "contract hiring",
    )
    return "Staffing & Recruitment" if any(term in text for term in staffing_terms) else "Nexplan — Enterprise Planning"


def score_opportunity(source_count, latest_date, business_impact, credibility_values, mapped_capability, today=None):
    """Return transparent component scores and total (0-100)."""
    today = today or date.today()
    frequency = min(max(int(source_count or 0), 0), 5) * 5

    latest = _date(latest_date)
    age_days = (today - latest).days if latest else None
    if age_days is None:
        recency = 0
    elif age_days <= 30:
        recency = 20
    elif age_days <= 90:
        recency = 15
    elif age_days <= 180:
        recency = 10
    else:
        recency = 5

    impact_text = _norm(business_impact)
    if any(term in impact_text for term in (
        "shutdown", "production halted", "missed order", "safety risk",
        "major disruption", "critical", "severe", "significant",
    )):
        impact = 25
    elif any(term in impact_text for term in (
        "cost", "productivity", "revenue", "delay", "capacity", "operational",
        "efficiency", "output", "turnover",
    )):
        impact = 18
    elif impact_text:
        impact = 10
    else:
        impact = 0

    quality_scores = []
    for label in credibility_values or []:
        label = _norm(label)
        if "high" in label:
            quality_scores.append(20)
        elif "moderate" in label:
            quality_scores.append(14)
        elif "limited" in label:
            quality_scores.append(8)
        elif label and "unclassified" in label:
            quality_scores.append(5)
    evidence = round(sum(quality_scores) / len(quality_scores)) if quality_scores else 0

    actionability = 10 if _truthy_text(mapped_capability) else 0
    components = {
        "Frequency": frequency,
        "Recency": recency,
        "Business impact": impact,
        "Evidence strength": evidence,
        "Actionability": actionability,
    }
    total = min(100, sum(components.values()))
    if total >= 70:
        priority = "High priority"
    elif total >= 45:
        priority = "Investigate"
    else:
        priority = "Monitor"
    return {"score": total, "priority": priority, "components": components}


def build_opportunity_priorities(research, mapped_opportunities, source_register, today=None):
    """Aggregate mapped capabilities and link each priority to its evidence rows."""
    today = today or date.today()
    research_rows = (research.to_dict("records") if hasattr(research, "to_dict") else list(research or []))
    mapped_rows = (mapped_opportunities.to_dict("records") if hasattr(mapped_opportunities, "to_dict") else list(mapped_opportunities or []))
    source_rows = (source_register.to_dict("records") if hasattr(source_register, "to_dict") else list(source_register or []))

    source_quality = {}
    for row in source_rows:
        url = _truthy_text(row.get("Source URL"))
        if url:
            source_quality[url] = _truthy_text(row.get("Source Credibility Assessment"))

    findings_by_id = {}
    for row in research_rows:
        rid = _truthy_text(row.get("Research ID"))
        if rid:
            findings_by_id[rid] = row

    groups = {}
    for mapping in mapped_rows:
        rid_text = _truthy_text(mapping.get("Related Research IDs"))
        ids = [rid.strip() for rid in rid_text.split(",") if rid.strip()]
        linked = [findings_by_id[rid] for rid in ids if rid in findings_by_id]
        if not linked and not _truthy_text(mapping.get("Supporting Source URLs")):
            continue
        key = tuple(_norm(mapping.get(col)) for col in (
            "Industry", "Market Need", "Proposed Product Capability", "Suggested Feature & Description"))
        group = groups.setdefault(key, {
            "Industry": _truthy_text(mapping.get("Industry")) or "Unclassified",
            "Market Need": _truthy_text(mapping.get("Market Need")),
            "Capability": _truthy_text(mapping.get("Proposed Product Capability")),
            "Suggested Feature": _truthy_text(mapping.get("Suggested Feature & Description")),
            "Business Value": _truthy_text(mapping.get("Expected Business Value")),
            "Priority": "",
            "Supporting Research IDs": set(),
            "Supporting Source URLs": set(),
            "Countries": set(),
            "Impacts": [],
            "Dates": [],
            "Credibility": [],
        })
        for finding in linked:
            if finding.get("Research ID"):
                group["Supporting Research IDs"].add(str(finding["Research ID"]))
            url = _truthy_text(finding.get("Source URL"))
            if url:
                group["Supporting Source URLs"].add(url)
                quality = source_quality.get(url)
                if quality:
                    group["Credibility"].append(quality)
            country = _truthy_text(finding.get("Country"))
            if country:
                group["Countries"].add(country)
            impact_text = _truthy_text(finding.get("Business Impact"))
            if impact_text:
                group["Impacts"].append(impact_text)
            date_value = _date(finding.get("Research Date")) or _date(finding.get("Last Seen"))
            if date_value and (not group["Dates"] or date_value > max(group["Dates"])):
                group["Dates"].append(date_value)
        extra_urls = _truthy_text(mapping.get("Supporting Source URLs"))
        for url in extra_urls.split(","):
            if url.strip():
                group["Supporting Source URLs"].add(url.strip())

    output = []
    for group in groups.values():
        urls = sorted(group["Supporting Source URLs"])
        latest = max(group["Dates"]).isoformat() if group["Dates"] else ""
        score = score_opportunity(
            len(urls), latest, " ".join(group["Impacts"]), group["Credibility"],
            group["Capability"], today=today,
        )
        group["Track"] = classify_track(group["Market Need"], group["Capability"], group["Suggested Feature"])
        group["Score"] = score["score"]
        group["Priority"] = score["priority"]
        group["Score Breakdown"] = score["components"]
        group["Latest Evidence"] = latest
        group["Source Count"] = len(urls)
        group["Country Count"] = len(group["Countries"])
        group["Supporting Research IDs"] = ", ".join(sorted(group["Supporting Research IDs"]))
        group["Supporting Source URLs"] = ", ".join(urls)
        group["Countries"] = ", ".join(sorted(group["Countries"]))
        group["Scoring Note"] = "Heuristic score; evidence breadth is a research signal, not proof of workforce shortage severity."
        output.append(group)

    priority_rank = {"High priority": 0, "Investigate": 1, "Monitor": 2}
    output.sort(key=lambda row: (priority_rank.get(row["Priority"], 3), -row["Score"], row["Industry"].casefold(), row["Market Need"].casefold()))
    return output
