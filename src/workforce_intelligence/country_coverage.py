"""Country-level research coverage metrics from explicit finding geography."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime

COUNTRY_ALIASES = {
    "usa": "United States", "us": "United States", "u.s.": "United States",
    "uk": "United Kingdom", "u.k.": "United Kingdom",
    "uae": "United Arab Emirates", "south korea": "South Korea",
    "republic of korea": "South Korea", "north korea": "North Korea",
    "russia": "Russia", "viet nam": "Vietnam", "czech republic": "Czechia",
    "ivory coast": "Côte d’Ivoire", "türkiye": "Turkey",
}
REGION_COUNTRIES = {
    "North America": {"United States", "Canada", "Mexico"},
    "Europe": {"United Kingdom", "Germany", "France", "Italy", "Spain", "Portugal", "Netherlands", "Belgium", "Switzerland", "Austria", "Sweden", "Norway", "Denmark", "Finland", "Poland", "Czechia", "Turkey", "Ukraine", "Russia", "Ireland", "Greece"},
    "Asia-Pacific": {"India", "China", "Japan", "South Korea", "North Korea", "Australia", "New Zealand", "Singapore", "Indonesia", "Malaysia", "Thailand", "Vietnam", "Philippines", "Taiwan", "Bangladesh", "Pakistan", "Sri Lanka"},
    "Middle East & Africa": {"United Arab Emirates", "Saudi Arabia", "Qatar", "Israel", "Egypt", "South Africa", "Nigeria", "Kenya", "Morocco", "Ghana", "Ethiopia"},
    "Latin America": {"Brazil", "Argentina", "Chile", "Colombia", "Peru"},
}
MANUFACTURING_TERMS = ("manufactur", "factory", "production", "industrial", "assembly", "plant", "semiconductor", "automotive", "machinery", "textile", "pharmaceutical", "chemical", "steel", "aerospace")


def _get(row, *keys):
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip() and str(value).strip().casefold() not in {"nan", "none", "unknown", "not specified"}:
            return value
    return None


def normalize_country(value):
    """Normalize common aliases while preserving unrecognized country labels."""
    if value is None:
        return ""
    country = " ".join(str(value).strip().split())
    if country.casefold() in {"", "unknown", "not specified", "global", "worldwide", "n/a", "nan"}:
        return ""
    alias = COUNTRY_ALIASES.get(country.casefold())
    return alias or country


def country_region(country):
    """Return a broad region for known countries; otherwise an explicit fallback."""
    for region, members in REGION_COUNTRIES.items():
        if country in members:
            return region
    return "Other / unclassified"


def _parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        try:
            return datetime.strptime(str(value), "%Y-%m").date()
        except ValueError:
            return None


def summarize_country_coverage(findings, target_countries=()):
    """Summarize only explicitly attributed finding countries; optional targets show zero coverage."""
    aggregates = {}
    for record in findings or []:
        country = normalize_country(_get(record, "country", "Country"))
        if not country:
            continue
        group = aggregates.setdefault(country, {
            "country": country, "region": country_region(country),
            "finding_count": 0, "industries": set(), "source_urls": set(),
            "problem_types": set(), "latest_evidence": None, "manufacturing_findings": 0,
        })
        group["finding_count"] += 1
        industry = str(_get(record, "industry", "Industry") or "").strip()
        if industry:
            group["industries"].add(industry)
        url = str(_get(record, "source_url", "Source URL") or "").strip()
        if url:
            group["source_urls"].add(url)
        problem = str(_get(record, "problem_type", "Identified Problem") or "").strip()
        if problem:
            group["problem_types"].add(problem)
        date_value = _parse_date(_get(record, "publication_date", "Publication date", "Research Date", "Last Seen"))
        if date_value and (group["latest_evidence"] is None or date_value > group["latest_evidence"]):
            group["latest_evidence"] = date_value
        sector_text = f"{industry} {problem}".casefold()
        if any(term in sector_text for term in MANUFACTURING_TERMS):
            group["manufacturing_findings"] += 1

    for target in target_countries or ():
        country = normalize_country(target)
        if country:
            aggregates.setdefault(country, {
                "country": country, "region": country_region(country),
                "finding_count": 0, "industries": set(), "source_urls": set(),
                "problem_types": set(), "latest_evidence": None, "manufacturing_findings": 0,
            })

    output = []
    for group in aggregates.values():
        latest = group["latest_evidence"]
        output.append({
            "Country": group["country"],
            "Region": group["region"],
            "Findings": group["finding_count"],
            "Distinct industries": len(group["industries"]),
            "Distinct sources": len(group["source_urls"]),
            "Distinct workforce problems": len(group["problem_types"]),
            "Manufacturing findings": group["manufacturing_findings"],
            "Latest evidence": latest.isoformat() if latest else "",
            "Industries": ", ".join(sorted(group["industries"], key=str.casefold)),
        })
    output.sort(key=lambda row: (-row["Findings"], row["Country"].casefold()))
    return output


def build_country_industry_matrix(findings, target_countries=()):
    """Return nested counts country -> industry -> finding count, optionally including zero targets."""
    matrix = defaultdict(lambda: defaultdict(int))
    for record in findings or []:
        country = normalize_country(_get(record, "country", "Country"))
        industry = str(_get(record, "industry", "Industry") or "Unclassified").strip()
        if country:
            matrix[country][industry] += 1
    for target in target_countries or ():
        country = normalize_country(target)
        if country:
            matrix.setdefault(country, defaultdict(int))
    return {country: dict(sorted(industry_counts.items(), key=lambda item: item[0].casefold()))
            for country, industry_counts in sorted(matrix.items(), key=lambda item: item[0].casefold())}
