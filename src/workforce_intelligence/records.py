"""Finding and source metadata normalization and quality checks."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any
from urllib.parse import urlparse

FINDING_COLUMNS = [
    "problem_type", "description", "country", "region", "industry",
    "sub_industry", "company", "source_name", "source_url",
    "publication_date", "data_period", "review_status",
]
SOURCE_COLUMNS = [
    "Source title", "Source URL", "Industry searched", "Country searched",
    "Actual geographic scope", "Region", "Publication date",
    "Collection status", "Relevance status", "Verification status", "Review notes",
]


def valid_http_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def normalize_finding(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize allowed workbook fields; never infer geography from search terms."""
    result = {column: item.get(column) for column in FINDING_COLUMNS}
    for key in ("problem_type", "description", "industry", "source_name"):
        if result[key] is not None:
            result[key] = str(result[key]).strip() or None
    if result["source_url"] and not valid_http_url(result["source_url"]):
        raise ValueError("source_url must be a valid HTTP(S) URL")
    if result["country"] in {"Not specified", "Unknown", ""}:
        result["country"] = None
    if result["region"] in {"Not specified", "Unknown", ""}:
        result["region"] = None
    return result


def finding_key(item: dict[str, Any]) -> tuple[str, str, str, str]:
    return tuple(str(item.get(k) or "").strip().casefold() for k in
                 ("problem_type", "country", "source_url", "description"))


def deduplicate_findings(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    unique = []
    for raw in items:
        item = normalize_finding(raw)
        key = finding_key(item)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def publication_year(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip()
    try:
        return date.fromisoformat(text[:10]).year
    except ValueError:
        try:
            return int(text[:4]) if text[:4].isdigit() else None
        except (TypeError, ValueError):
            return None
