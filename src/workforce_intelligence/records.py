"""Workbook schema, normalization and duplicate removal."""
from urllib.parse import urlparse
FINDING_COLUMNS = ["problem_type", "description", "business_impact", "country", "region", "industry", "sub_industry", "company", "source_name", "source_url", "source_platform", "publication_date", "data_period", "review_status"]
SOURCE_COLUMNS = ["Source title", "Source URL", "Source platform", "Candidate source class (domain heuristic)", "Industry searched", "Country searched", "Actual geographic scope", "Region", "Publication date", "Search result date", "Collection status", "Relevance status", "Source Credibility Assessment"]

def valid_http_url(value):
    if not isinstance(value, str):
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

def normalize_finding(item):
    row = {column: item.get(column) for column in FINDING_COLUMNS}
    for key in ("problem_type", "description", "industry", "source_name"):
        if row[key] is not None:
            row[key] = str(row[key]).strip() or None
    if row["source_url"] and not valid_http_url(row["source_url"]):
        raise ValueError("source_url must be a valid HTTP(S) URL")
    if str(row.get("source_platform") or "").casefold() == "linkedin":
        if not valid_http_url(row["source_url"]):
            raise ValueError("LinkedIn findings require their original source_url")
        host = (urlparse(row["source_url"]).hostname or "").lower().removeprefix("www.")
        if host != "linkedin.com" and not host.endswith(".linkedin.com"):
            raise ValueError("LinkedIn findings must retain a direct LinkedIn URL")
    for key in ("country", "region"):
        if row[key] in {"Not specified", "Unknown", ""}:
            row[key] = None
    return row

def deduplicate_findings(items):
    seen, result = set(), []
    for raw in items:
        row = normalize_finding(raw)
        key = tuple(str(row.get(field) or "").strip().casefold() for field in ("problem_type", "country", "source_url", "description"))
        if key not in seen:
            seen.add(key)
            result.append(row)
    return result
