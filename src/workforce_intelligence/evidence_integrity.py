"""Lightweight cross-sheet evidence traceability checks for manager review."""
from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

DETAIL_LIMIT = 50
_TRACKING_KEYS = {"fbclid", "gclid", "ref", "source", "campaign"}


def _records(value):
    if value is None:
        return []
    if hasattr(value, "to_dict"):
        try:
            return value.to_dict(orient="records")
        except TypeError:
            pass
    if isinstance(value, (list, tuple)):
        return [row for row in value if isinstance(row, dict)]
    return []


def _clean(value):
    text = str(value or "").strip()
    return "" if text.casefold() in {"nan", "none", "null"} else text


def _split_ids(value):
    values = value if isinstance(value, (list, tuple, set)) else _clean(value).split(",")
    return [_clean(item) for item in values if _clean(item)]


def _split_urls(value):
    return [part.strip() for part in _clean(value).split(",") if part.strip()]


def _url_key(value):
    """Normalize URL matching without changing source links shown to users."""
    text = _clean(value)
    if not text:
        return None
    try:
        parts = urlsplit(text)
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
            return None
        host = parts.hostname.lower()
        port = parts.port
        if port and not ((parts.scheme.lower() == "http" and port == 80) or (parts.scheme.lower() == "https" and port == 443)):
            host = f"{host}:{port}"
        path = parts.path.rstrip("/") or "/"
        query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                 if not k.casefold().startswith("utm_") and k.casefold() not in _TRACKING_KEYS]
        query.sort()
        return urlunsplit((parts.scheme.lower(), host, path, urlencode(query, doseq=True), ""))
    except (TypeError, ValueError):
        return None


def audit_evidence_integrity(research, source_register, opportunities=None):
    """Return metrics and capped details for cross-sheet traceability issues.

    Checks identifiers and links only; it does not validate source truth or AI interpretation.
    """
    research_rows = _records(research)
    source_rows = _records(source_register)
    opportunity_rows = _records(opportunities)
    metrics = {
        "duplicate_research_ids": 0,
        "findings_missing_research_id": 0,
        "findings_missing_source_url": 0,
        "findings_invalid_source_url": 0,
        "findings_urls_not_in_source_register": 0,
        "findings_missing_source_id": 0,
        "findings_source_id_mismatch": 0,
        "duplicate_source_register_urls": 0,
        "source_register_missing_urls": 0,
        "source_register_invalid_urls": 0,
        "duplicate_source_ids": 0,
        "source_register_unlinked": 0,
        "source_register_unknown_research_ids": 0,
        "source_register_link_mismatch": 0,
        "opportunity_unknown_research_ids": 0,
        "opportunity_urls_not_in_source_register": 0,
        "opportunity_research_source_mismatch": 0,
    }
    issues = []
    warning_count = 0
    info_count = 0

    def add(severity, issue, record, details, metric):
        nonlocal warning_count, info_count
        metrics[metric] += 1
        if severity == "Warning":
            warning_count += 1
        else:
            info_count += 1
        issues.append({"Severity": severity, "Issue": issue, "Record": record, "Details": details})

    research_by_id = {}
    for row in research_rows:
        rid = _clean(row.get("Research ID"))
        rid_key = rid.casefold()
        url = _clean(row.get("Source URL"))
        url_key = _url_key(url)
        if rid:
            research_by_id.setdefault(rid_key, []).append(row)
        else:
            add("Warning", "Missing Research ID", url or "Research row", "The research record has no identifier.", "findings_missing_research_id")
        if not url:
            add("Warning", "Missing Source URL", rid or "Research row", "No source link is present on the research record.", "findings_missing_source_url")
        elif not url_key:
            add("Warning", "Invalid Source URL", rid or url, "Source URL is not a valid public HTTP(S) URL.", "findings_invalid_source_url")

    for rid_key, rows in research_by_id.items():
        if len(rows) > 1:
            add("Warning", "Duplicate Research ID", _clean(rows[0].get("Research ID")), f"Identifier appears on {len(rows)} research rows.", "duplicate_research_ids")

    register_by_url = {}
    register_by_id = {}
    register_url_keys = set()
    for row in source_rows:
        url = _clean(row.get("Source URL"))
        url_key = _url_key(url)
        sid = _clean(row.get("Source ID"))
        linked_ids = _split_ids(row.get("Related Research IDs"))
        if sid:
            register_by_id.setdefault(sid.casefold(), []).append(url_key)
        if not url:
            add("Warning", "Missing Source Register URL", sid or "Source row", "The source-register record has no URL.", "source_register_missing_urls")
        elif not url_key:
            add("Warning", "Invalid Source Register URL", sid or url, "Source Register URL is not a valid public HTTP(S) URL.", "source_register_invalid_urls")
        else:
            register_by_url.setdefault(url_key, []).append({"row": row, "source_id": sid, "linked_ids": linked_ids, "url": url})
            register_url_keys.add(url_key)
        if not linked_ids:
            add("Info", "Source Register entry unlinked", url or sid or "Source row", "Source has no Related Research IDs in the current register.", "source_register_unlinked")
        for linked_id in linked_ids:
            linked_research = research_by_id.get(linked_id.casefold(), [])
            if not linked_research:
                add("Warning", "Source Register references unknown Research ID", linked_id, f"Referenced by source {url or sid or 'without URL'}.", "source_register_unknown_research_ids")
            elif url_key:
                for finding in linked_research:
                    finding_url_key = _url_key(finding.get("Source URL"))
                    if finding_url_key and finding_url_key != url_key:
                        add("Warning", "Source Register research link mismatch", linked_id, f"The source register URL {url} differs from the research URL {finding.get('Source URL')}.", "source_register_link_mismatch")

    for url_key, rows in register_by_url.items():
        if len(rows) > 1:
            add("Warning", "Duplicate Source Register URL", rows[0]["url"], f"URL appears on {len(rows)} source rows.", "duplicate_source_register_urls")
    for sid_key, url_keys in register_by_id.items():
        if len(set(url_keys)) > 1:
            add("Warning", "Duplicate Source ID", sid_key, f"Source ID is used for {len(set(url_keys))} distinct URLs.", "duplicate_source_ids")

    for row in research_rows:
        rid = _clean(row.get("Research ID")) or "Research row"
        url = _clean(row.get("Source URL"))
        url_key = _url_key(url)
        sid = _clean(row.get("Source ID"))
        if url_key and url_key not in register_url_keys:
            add("Warning", "Research URL missing from Source Register", rid, url, "findings_urls_not_in_source_register")
        if url_key and url_key in register_by_url:
            expected_ids = {item["source_id"].casefold() for item in register_by_url[url_key] if item["source_id"]}
            if not sid:
                add("Warning", "Missing Source ID", rid, "The research record links to a registered source but has no Source ID.", "findings_missing_source_id")
            elif expected_ids and sid.casefold() not in expected_ids:
                add("Warning", "Source ID mismatch", rid, f"Research Source ID {sid} does not match register ID(s): {', '.join(sorted(expected_ids))}.", "findings_source_id_mismatch")

    for row in opportunity_rows:
        oid = _clean(row.get("Opportunity ID")) or _clean(row.get("Identified Market Problem")) or "Opportunity row"
        linked_ids = _split_ids(row.get("Related Research IDs"))
        opportunity_urls = _split_urls(row.get("Supporting Source URLs"))
        opportunity_url_keys = {key for url in opportunity_urls if (key := _url_key(url))}
        for linked_id in linked_ids:
            linked_research = research_by_id.get(linked_id.casefold(), [])
            if not linked_research:
                add("Warning", "Opportunity references unknown Research ID", oid, linked_id, "opportunity_unknown_research_ids")
            elif opportunity_url_keys:
                for finding in linked_research:
                    finding_url_key = _url_key(finding.get("Source URL"))
                    if finding_url_key and finding_url_key not in opportunity_url_keys:
                        add("Warning", "Opportunity research/source mismatch", oid, f"Research ID {linked_id} links to {finding.get('Source URL')} not listed among opportunity source URLs.", "opportunity_research_source_mismatch")
        for url in opportunity_urls:
            url_key = _url_key(url)
            if url_key and url_key not in register_url_keys:
                add("Warning", "Opportunity source URL missing from Source Register", oid, url, "opportunity_urls_not_in_source_register")
            elif url and not url_key:
                add("Warning", "Invalid opportunity source URL", oid, url, "opportunity_urls_not_in_source_register")

    return {
        "metrics": metrics,
        "warning_count": warning_count,
        "info_count": info_count,
        "issues": issues[:DETAIL_LIMIT],
        "details_truncated": len(issues) > DETAIL_LIMIT,
        "total_issue_details": len(issues),
    }
