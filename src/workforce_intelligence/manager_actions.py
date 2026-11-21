"""Explainable manager action recommendations from workforce research signals."""
from __future__ import annotations

from datetime import date


def _text(value):
    value = str(value or "").strip()
    return "" if value.casefold() in {"nan", "none", "null"} else value


def _date(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _terms(text, phrases):
    text = text.casefold()
    return any(phrase in text for phrase in phrases)


def recommend_manager_actions(research, weekly_trends=None, today=None):
    """Rank distinct industry/problem groups and explain score + suggested next step.

    Scores are decision-support heuristics. They do not estimate shortage severity.
    Input accepts pandas DataFrames or iterable dictionaries.
    """
    today = today or date.today()
    research_rows = research.to_dict("records") if hasattr(research, "to_dict") else list(research or [])
    trend_rows = weekly_trends.to_dict("records") if hasattr(weekly_trends, "to_dict") else list(weekly_trends or [])
    trends = {}
    for row in trend_rows:
        key = (_text(row.get("Industry")).casefold(), _text(row.get("Workforce Problem")).casefold())
        trends[key] = row

    groups = {}
    for row in research_rows:
        industry = _text(row.get("Industry")) or "Unclassified"
        problem = _text(row.get("Identified Problem")) or _text(row.get("Problem Type")) or "Unclassified workforce problem"
        key = (industry.casefold(), problem.casefold())
        group = groups.setdefault(key, {
            "industry": industry, "problem": problem, "sources": set(), "countries": set(),
            "impacts": [], "dates": [], "statuses": set(), "weeks": set(), "records": 0,
        })
        group["records"] += 1
        source = _text(row.get("Source URL"))
        if source:
            group["sources"].add(source)
        country = _text(row.get("Country"))
        if country and country.casefold() not in {"unknown", "not specified", "global"}:
            group["countries"].add(country)
        impact = _text(row.get("Business Impact"))
        if impact:
            group["impacts"].append(impact)
        for date_key in ("Research Date", "Last Seen"):
            parsed = _date(row.get(date_key))
            if parsed:
                group["dates"].append(parsed)
        status = _text(row.get("Weekly Status"))
        if status:
            group["statuses"].add(status)
        weeks = row.get("Weeks Seen")
        if isinstance(weeks, str):
            group["weeks"].update(v.strip() for v in weeks.split(",") if v.strip())
        elif weeks:
            group["weeks"].update(str(v) for v in weeks)

    output = []
    for group in groups.values():
        sources, countries, impacts = group["sources"], group["countries"], " ".join(group["impacts"]).casefold()
        latest = max(group["dates"]) if group["dates"] else None
        age = (today - latest).days if latest else None
        recency_points = 20 if age is not None and age <= 30 else 12 if age is not None and age <= 90 else 5 if age is not None else 0
        source_points = min(25, len(sources) * 5)
        country_points = min(15, len(countries) * 3)
        repeat_points = min(15, len(group["weeks"]) * 5) if group["weeks"] else min(10, max(0, group["records"] - 1) * 3)
        impact_points = 25 if _terms(impacts, ("shutdown", "production halted", "safety risk", "critical", "severe", "major disruption")) else 18 if _terms(impacts, ("delay", "cost", "productivity", "capacity", "revenue", "turnover", "efficiency", "output")) else 8 if impacts else 0
        total = min(100, source_points + country_points + repeat_points + recency_points + impact_points)
        trend = trends.get((group["industry"].casefold(), group["problem"].casefold()), {})
        momentum = _text(trend.get("Signal Momentum"))
        if "worsening" in momentum.casefold() or "growing" in momentum.casefold() or "emerging" in momentum.casefold():
            total = min(100, total + 10)
            momentum_bonus = 10
        else:
            momentum_bonus = 0

        text_blob = f"{group['problem']} {impacts} {group['industry']}".casefold()
        if _terms(text_blob, ("hiring", "recruit", "vacancy", "time-to-fill", "staffing", "talent shortage", "labor shortage", "labour shortage")):
            action = "Validate hiring demand and pipeline"
            next_step = "Interview hiring managers; compare open roles, time-to-fill and attrition; identify the hardest-to-fill roles."
        elif _terms(text_blob, ("skill", "skills gap", "training", "upskill", "reskill", "capability")):
            action = "Run a skills-gap assessment"
            next_step = "Map critical roles to required skills; validate gaps with supervisors and review internal training or redeployment options."
        elif _terms(text_blob, ("automation", "robot", "digital", "technology", "ai", "system")):
            action = "Assess technology and workflow options"
            next_step = "Identify the affected workflow, baseline manual effort and quality, and pilot a low-risk technology or process change."
        elif _terms(text_blob, ("maintenance", "equipment", "production", "manufacturing", "factory", "plant", "quality")):
            action = "Investigate operational root causes"
            next_step = "Review downtime, scrap, throughput and maintenance records with operations; validate the problem before proposing a solution."
        elif _terms(text_blob, ("retention", "turnover", "burnout", "wellbeing", "engagement")):
            action = "Review retention and workforce experience"
            next_step = "Segment turnover and employee feedback by role/site; validate drivers and prioritize one retention intervention."
        else:
            action = "Validate problem with stakeholders"
            next_step = "Confirm scope, affected roles/sites, business impact and evidence with a stakeholder before committing resources."

        if total >= 70:
            priority = "Act / validate now"
        elif total >= 45:
            priority = "Investigate next"
        else:
            priority = "Monitor"
        explanation = [
            f"{len(sources)} distinct source(s) (+{source_points}/25)",
            f"{len(countries)} country/countries (+{country_points}/15)",
            f"{len(group['weeks']) or max(0, group['records'] - 1)} repeat observation(s) (+{repeat_points}/15)",
            f"Recency (+{recency_points}/20)",
            f"Impact wording (+{impact_points}/25)",
        ]
        if momentum_bonus:
            explanation.append(f"Weekly momentum bonus (+{momentum_bonus})")
        output.append({
            "Rank Score": total, "Priority": priority, "Industry": group["industry"],
            "Workforce Problem": group["problem"], "Manager Action": action,
            "Recommended Next Step": next_step, "Source Count": len(sources),
            "Country Count": len(countries), "Latest Evidence": latest.isoformat() if latest else "",
            "Weekly Momentum": momentum or "No weekly signal", "Score Rationale": "; ".join(explanation),
            "Evidence URLs": sorted(sources), "Countries": sorted(countries),
        })
    output.sort(key=lambda row: (-row["Rank Score"], row["Industry"].casefold(), row["Workforce Problem"].casefold()))
    return output
