"""Emerging skill signals inferred from global workforce research findings.

Classification is keyword-based and transparent. Trend labels describe research
coverage, not validated labor-market demand or hiring volume.
"""
from __future__ import annotations

from datetime import date, timedelta
import re

SKILL_TAXONOMY = {
    "Industrial automation & robotics": {
        "terms": ["robotics", "robotic", "automation", "automated", "plc", "scada", "control systems"],
        "manufacturing": True,
    },
    "Advanced manufacturing & digital operations": {
        "terms": ["digital twin", "industry 4.0", "smart manufacturing", "mes", "industrial iot", "iot"],
        "manufacturing": True,
    },
    "Maintenance & reliability": {
        "terms": ["maintenance", "predictive maintenance", "reliability", "asset reliability"],
        "manufacturing": True,
    },
    "Quality & process engineering": {
        "terms": ["quality", "six sigma", "process engineering", "continuous improvement"],
        "manufacturing": True,
    },
    "Skilled trades & production": {
        "terms": ["machinist", "cnc", "welding", "welder", "production technician", "skilled trades", "operator"],
        "manufacturing": True,
    },
    "Industrial AI, data & analytics": {
        "terms": ["artificial intelligence", "machine learning", "data analytics", "data science", "analytics", "ai skills"],
        "manufacturing": True,
    },
    "Supply chain & logistics": {
        "terms": ["supply chain", "logistics", "procurement", "inventory", "warehouse"],
        "manufacturing": False,
    },
    "Safety, EHS & compliance": {
        "terms": ["safety", "ehs", "occupational health", "compliance", "risk management"],
        "manufacturing": True,
    },
    "Energy & sustainability": {
        "terms": ["sustainability", "energy efficiency", "renewable energy", "decarbonization", "carbon"],
        "manufacturing": True,
    },
    "Cybersecurity": {
        "terms": ["cybersecurity", "cyber security", "security engineer", "information security"],
        "manufacturing": False,
    },
    "Cloud & software engineering": {
        "terms": ["cloud", "software engineering", "devops", "software developer", "programming"],
        "manufacturing": False,
    },
    "Project & change management": {
        "terms": ["project management", "change management", "transformation", "program management"],
        "manufacturing": False,
    },
    "Leadership & people management": {
        "terms": ["leadership", "management skills", "people management", "supervisor", "manager"],
        "manufacturing": False,
    },
    "Communication & collaboration": {
        "terms": ["communication", "collaboration", "teamwork", "interpersonal"],
        "manufacturing": False,
    },
    "Customer, sales & service": {
        "terms": ["customer service", "sales skills", "customer experience", "account management"],
        "manufacturing": False,
    },
    "Healthcare & clinical skills": {
        "terms": ["clinical", "nursing", "healthcare", "patient care"],
        "manufacturing": False,
    },
    "Finance & accounting": {
        "terms": ["accounting", "financial analysis", "finance skills", "financial planning"],
        "manufacturing": False,
    },
    "Learning agility & reskilling": {
        "terms": ["upskilling", "reskilling", "skills gap", "skill gap", "training", "learning agility"],
        "manufacturing": False,
    },
}

MANUFACTURING_TERMS = (
    "manufacturing", "factory", "production", "industrial", "assembly", "machinery",
    "automotive", "semiconductor", "textile", "chemical", "steel", "aerospace",
    "pharmaceutical", "food processing", "plant", "cnc", "robotics",
)


def _text(record):
    return " ".join(str(record.get(key) or "") for key in (
        "problem_type", "description", "industry", "sub_industry", "skill", "skills"
    )).casefold()


def _week(value):
    try:
        parsed = date.fromisoformat(str(value).strip()[:10])
        return (parsed - timedelta(days=parsed.weekday())).isoformat()
    except (ValueError, TypeError):
        return None


def _weeks(record):
    values = record.get("weeks_seen") or []
    if isinstance(values, str):
        values = [v.strip() for v in values.split(",") if v.strip()]
    weeks = {_week(value) for value in values}
    for key in ("first_seen_week", "last_seen_week", "first_seen", "last_seen"):
        parsed = _week(record.get(key))
        if parsed:
            weeks.add(parsed)
    return {value for value in weeks if value}


def _country(record):
    value = record.get("country")
    if value is None or str(value).strip().casefold() in {"", "unknown", "not specified", "global"}:
        return ""
    return str(value).strip()


def analyze_skill_trends(records, reference_date=None):
    """Aggregate skills by distinct sources, industries, countries and observation weeks.

    Rows without matching skill keywords are intentionally omitted. A one-source
    signal is never labeled Emerging; recent emergence requires corroboration.
    """
    today = date.fromisoformat(str(reference_date)[:10]) if reference_date else date.today()
    current_week = (today - timedelta(days=today.weekday())).isoformat()
    aggregates = {}
    for record in records or []:
        text = _text(record)
        industry = str(record.get("industry") or "Unclassified").strip()
        country = _country(record)
        source = str(record.get("source_url") or record.get("source_name") or "").strip()
        observed_weeks = _weeks(record)
        first_seen = str(record.get("first_seen") or record.get("first_seen_week") or "").strip()
        last_seen = str(record.get("last_seen") or record.get("last_seen_week") or "").strip()
        manufacturing = any(term in text for term in MANUFACTURING_TERMS)
        matched = []
        for skill, info in SKILL_TAXONOMY.items():
            if any(term in text for term in info["terms"]):
                matched.append(skill)
        for skill in matched:
            bucket = aggregates.setdefault(skill, {
                "skill": skill, "sources": set(), "industries": set(),
                "countries": set(), "weeks": set(), "manufacturing_records": 0,
                "first_seen": None, "last_seen": None,
            })
            if source:
                bucket["sources"].add(source)
            bucket["industries"].add(industry)
            if country:
                bucket["countries"].add(country)
            bucket["weeks"].update(observed_weeks)
            if manufacturing or SKILL_TAXONOMY[skill]["manufacturing"]:
                bucket["manufacturing_records"] += 1
            if first_seen and (bucket["first_seen"] is None or first_seen < bucket["first_seen"]):
                bucket["first_seen"] = first_seen
            if last_seen and (bucket["last_seen"] is None or last_seen > bucket["last_seen"]):
                bucket["last_seen"] = last_seen

    results = []
    for bucket in aggregates.values():
        sources, industries, countries, weeks = (
            bucket["sources"], bucket["industries"], bucket["countries"], bucket["weeks"]
        )
        source_count, industry_count, country_count, week_count = (
            len(sources), len(industries), len(countries), len(weeks)
        )
        recent = False
        if bucket["last_seen"]:
            try:
                recent = (today - date.fromisoformat(bucket["last_seen"][:10])).days <= 60
            except ValueError:
                pass
        recent = recent or current_week in weeks
        emerging = recent and source_count >= 2 and week_count <= 2
        persistent = week_count >= 3
        if emerging:
            trend = "Emerging signal"
        elif persistent:
            trend = "Persistent signal"
        elif industry_count >= 2:
            trend = "Cross-industry signal"
        elif recent:
            trend = "Recent signal"
        else:
            trend = "Historical signal"
        score = min(100, source_count * 12 + industry_count * 10 + country_count * 6 + week_count * 4 + (12 if recent else 0))
        results.append({
            "skill": bucket["skill"], "trend": trend, "signal_score": score,
            "source_count": source_count, "industry_count": industry_count,
            "country_count": country_count, "weeks_observed": week_count,
            "industries": sorted(industries), "countries": sorted(countries),
            "manufacturing_records": bucket["manufacturing_records"],
            "first_seen": bucket["first_seen"] or "", "last_seen": bucket["last_seen"] or "",
        })
    results.sort(key=lambda row: (-row["signal_score"], row["skill"].casefold()))
    return results
