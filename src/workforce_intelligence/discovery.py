"""Tavily public-source discovery. Results are candidates, not verified sources."""
import os
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

TAVILY_URL = "https://api.tavily.com/search"
TERMS = '"workforce shortage" OR "labour shortage" OR "labor shortage" OR "skills gap" OR "skills shortage" OR "recruitment difficulties" OR "employee retention" OR "talent shortage"'
LINKEDIN_TERMS = '"workforce shortage" OR "skills gap" OR "hiring difficulties" OR "production workers" OR "talent shortage"'


def source_platform(url):
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    return "LinkedIn" if host == "linkedin.com" or host.endswith(".linkedin.com") else "Web"


def classify_source_domain(domain):
    host = (domain or "").lower().split(":")[0].removeprefix("www.")
    if host.endswith(".gov") or ".gov." in host or host.endswith(".gov.uk") or host.endswith(".gov.in"):
        return "Government domain (heuristic)"
    if any(token in host for token in ("oecd.org", "ilo.org", "worldbank.org", "weforum.org", "europa.eu", "un.org")):
        return "Intergovernmental / multilateral (heuristic)"
    if host.endswith(".edu") or host.endswith(".ac.uk") or host.endswith(".ac.in"):
        return "Academic domain (heuristic)"
    if any(token in host for token in ("mckinsey.com", "deloitte.com", "pwc.com", "ey.com", "kpmg.com", "bcg.com")):
        return "Research / consulting publisher (heuristic)"
    if any(token in host for token in ("manufacturers", "industry", "association", "federation", "chamber")):
        return "Possible industry body (heuristic)"
    return "Other / unclassified"


def make_query(industry, country=None):
    geography = f" {country.strip()}" if country and country.strip() else " global"
    return f'{industry}{geography} workforce challenges {TERMS} report research data'


def _post_search(client, payload, timeout, retries=3):
    """Retry transient rate-limit and server errors with short exponential backoff."""
    for attempt in range(retries):
        response = client.post(TAVILY_URL, json=payload, timeout=timeout)
        if response.status_code not in (429, 500, 502, 503, 504) or attempt == retries - 1:
            response.raise_for_status()
            return response
        time.sleep(2 ** attempt)
    raise RuntimeError("Tavily search failed after retries.")


def discover_sources(industries, api_key=None, country=None, max_results=8,
                     timeout=45, session=None, time_range="week", min_search_score=0.30):
    key = api_key or os.getenv("TAVILY_API_KEY")
    if not key:
        raise ValueError("Set TAVILY_API_KEY or pass api_key.")
    if not 1 <= max_results <= 20:
        raise ValueError("max_results must be between 1 and 20.")
    if time_range not in {"day", "week", "month", "year"}:
        raise ValueError("time_range must be day, week, month or year.")
    client = session or requests.Session()
    found = {}
    # Accept one or more comma-separated search geographies. Each geography is
    # still only a discovery lead; extraction must find explicit source evidence.
    search_countries = [part.strip() for part in str(country or "").split(",") if part.strip()] or [None]
    for industry in industries:
      for search_country in search_countries:
        queries = [
            (make_query(industry, search_country), "Web"),
            (f'site:linkedin.com/posts OR site:linkedin.com/pulse "{industry}" {search_country or "global"} {LINKEDIN_TERMS}', "LinkedIn"),
        ]
        for query, requested_platform in queries:
            payload = {
                "api_key": key, "query": query, "topic": "general",
                "search_depth": "basic", "max_results": max_results,
                "include_answer": False, "include_raw_content": False,
                "time_range": time_range,
            }
            response = _post_search(client, payload, timeout)
            for item in response.json().get("results", []):
                url = (item.get("url") or "").strip()
                parsed = urlparse(url)
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    continue
                host = (parsed.hostname or "").lower().removeprefix("www.")
                platform = "LinkedIn" if host == "linkedin.com" or host.endswith(".linkedin.com") else "Web"
                if requested_platform == "LinkedIn" and platform != "LinkedIn":
                    continue
                score = item.get("score")
                if score is not None and score < min_search_score:
                    continue
                title_snippet = f"{item.get('title') or ''} {item.get('content') or ''}".casefold()
                relevance_terms = ("workforce", "worker", "employee", "labor", "labour", "talent", "hiring", "recruit", "skill", "staff", "vacanc", "attrition", "retention", "production", "manufactur")
                if not any(term in title_snippet for term in relevance_terms):
                    continue
                found.setdefault(url, {
                    "industry": industry, "country_searched": search_country,
                    "title": item.get("title"), "url": url,
                    "domain": parsed.netloc.lower(), "source_platform": platform,
                    "source_class": classify_source_domain(parsed.netloc),
                    "snippet": item.get("content"), "search_score": item.get("score"),
                    "search_published_date": item.get("published_date"),
                    "discovered_at": datetime.now(timezone.utc).isoformat(),
                    "discovery_status": "Candidate - not verified",
                })
    priority = {
        "Government domain (heuristic)": 0,
        "Intergovernmental / multilateral (heuristic)": 1,
        "Academic domain (heuristic)": 2,
        "Research / consulting publisher (heuristic)": 3,
        "Possible industry body (heuristic)": 4,
        "Other / unclassified": 5,
    }
    return sorted(found.values(), key=lambda item: (
        priority.get(item.get("source_class"), 9),
        -(item.get("search_score") or 0),
    ))
