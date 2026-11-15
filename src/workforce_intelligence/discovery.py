"""Public-source discovery using Tavily's search API."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import requests

TAVILY_URL = "https://api.tavily.com/search"
WORKFORCE_TERMS = (
    '"workforce shortage" OR "labour shortage" OR "labor shortage" OR '
    '"skills gap" OR "skills shortage" OR "recruitment difficulties" OR '
    '"employee retention" OR "talent shortage"'
)


def make_query(industry: str, country: str | None = None) -> str:
    geography = f" {country.strip()}" if country and country.strip() else " global"
    return f'{industry}{geography} workforce challenges {WORKFORCE_TERMS} report research data'


def discover_sources(
    industries: tuple[str, ...] | list[str],
    api_key: str | None = None,
    country: str | None = None,
    max_results: int = 5,
    timeout: int = 45,
    session: requests.Session | None = None,
) -> list[dict[str, Any]]:
    """Return candidate sources only; discovery is not source verification."""
    key = api_key or os.getenv("TAVILY_API_KEY")
    if not key:
        raise ValueError("Set TAVILY_API_KEY or pass api_key.")
    if not 1 <= max_results <= 20:
        raise ValueError("max_results must be between 1 and 20.")
    client = session or requests.Session()
    found: dict[str, dict[str, Any]] = {}
    for industry in industries:
        query = make_query(industry, country)
        response = client.post(
            TAVILY_URL,
            json={"api_key": key, "query": query, "topic": "general",
                  "search_depth": "basic", "max_results": max_results,
                  "include_answer": False, "include_raw_content": False},
            timeout=timeout,
        )
        response.raise_for_status()
        for item in response.json().get("results", []):
            url = (item.get("url") or "").strip()
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                continue
            if url not in found:
                found[url] = {
                    "industry": industry,
                    "country_searched": country,
                    "title": item.get("title"),
                    "url": url,
                    "domain": parsed.netloc.lower(),
                    "snippet": item.get("content"),
                    "search_score": item.get("score"),
                    "search_published_date": item.get("published_date"),
                    "discovered_at": datetime.now(timezone.utc).isoformat(),
                    "discovery_status": "Candidate - not verified",
                }
    return list(found.values())
