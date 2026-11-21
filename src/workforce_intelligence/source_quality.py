"""Deterministic source quality, relevance, recency and geography checks.

Scores are triage aids, not truth or credibility guarantees. This module does not
discard records by default; it annotates candidates so downstream workflows can
apply review thresholds transparently.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

TRACKING_KEYS = {"fbclid", "gclid", "dclid", "mc_cid", "mc_eid", "ref", "ref_src"}
TRACKING_PREFIXES = ("utm_",)
WORKFORCE_TERMS = {
    "workforce": 3, "worker": 2, "employee": 2, "labor": 2, "labour": 2,
    "talent": 2, "hiring": 2, "recruit": 2, "skill": 2, "staff": 2,
    "vacancy": 2, "vacancies": 2, "attrition": 2, "retention": 2,
    "shortage": 2, "layoff": 2, "layoffs": 2, "wage": 1, "pay": 1,
    "productivity": 1, "training": 1, "automation": 1,
}
MANUFACTURING_TERMS = {
    "manufacturing": 4, "manufacture": 3, "factory": 3, "plant": 2,
    "production": 2, "assembly": 2, "industrial": 2, "machinery": 2,
    "automotive": 2, "automobile": 2, "semiconductor": 3, "electronics": 2,
    "metal": 2, "steel": 2, "chemical": 2, "pharmaceutical": 2,
    "food processing": 3, "textile": 2, "aerospace": 2, "supply chain": 1,
}
QUALITY_TIERS = (
    (("gov",), 4, "Government / official domain (heuristic)"),
    (("edu",), 3, "Academic domain (heuristic)"),
    (("ac.",), 3, "Academic domain (heuristic)"),
    (("ilo.org", "oecd.org", "worldbank.org", "un.org", "europa.eu"), 4, "Multilateral / intergovernmental (heuristic)"),
    (("reuters.com", "apnews.com", "bbc.com", "ft.com", "wsj.com", "nytimes.com"), 3, "Established news publisher (heuristic)"),
    (("mckinsey.com", "deloitte.com", "pwc.com", "ey.com", "kpmg.com", "bcg.com"), 2, "Consulting / research publisher (heuristic)"),
    (("association", "federation", "chamber", "industry"), 2, "Possible industry body (heuristic)"),
)

def canonicalize_url(url):
    """Normalize a URL and remove common tracking parameters."""
    if not isinstance(url, str) or not url.strip():
        return ""
    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return ""
    host = parsed.hostname.lower().removeprefix("www.")
    port = parsed.port
    netloc = host if not port or (parsed.scheme == "https" and port == 443) or (parsed.scheme == "http" and port == 80) else f"{host}:{port}"
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    kept = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
            if k.casefold() not in TRACKING_KEYS and not k.casefold().startswith(TRACKING_PREFIXES)]
    query = urlencode(sorted(kept))
    return urlunparse((parsed.scheme.lower(), netloc, path, "", query, ""))

def _tokens(text):
    return re.findall(r"[a-z0-9]+", str(text or "").casefold())

def _term_score(text, dictionary):
    tokens = set(_tokens(text))
    joined = str(text or "").casefold()
    return sum(weight for term, weight in dictionary.items()
               if (term in tokens if " " not in term else term in joined))

def _parse_date(value):
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(text[:10] if fmt == "%Y-%m-%d" else text, fmt).date()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None

def recency_assessment(publication_date, reference_date=None):
    """Return age and transparent recency band; unknown dates are not penalized."""
    published = _parse_date(publication_date)
    reference = reference_date or date.today()
    if not published:
        return {"publication_date_normalized": None, "age_days": None, "recency_score": None, "recency_label": "Date unknown"}
    age = max(0, (reference - published).days)
    if age <= 30:
        score, label = 4, "Recent (0–30 days)"
    elif age <= 180:
        score, label = 3, "Current (31–180 days)"
    elif age <= 365:
        score, label = 2, "Older (181–365 days)"
    elif age <= 730:
        score, label = 1, "Historical (1–2 years)"
    else:
        score, label = 0, "Older historical source (>2 years)"
    return {"publication_date_normalized": published.isoformat(), "age_days": age, "recency_score": score, "recency_label": label}

def source_quality_assessment(url, source_title="", publisher="", source_class=""):
    """Domain-based source triage; scores do not validate factual accuracy."""
    parsed = urlparse(canonicalize_url(url))
    host = parsed.hostname or ""
    text = f"{host} {publisher} {source_class}".casefold()
    score, label = 1, "Unclassified source (heuristic)"
    for patterns, value, tier in QUALITY_TIERS:
        if any(pattern in text for pattern in patterns):
            score, label = value, tier
            break
    if host.endswith(".gov") or ".gov." in host:
        score, label = 4, "Government / official domain (heuristic)"
    if host.endswith(".edu") or host.endswith(".ac.uk") or host.endswith(".ac.in"):
        score, label = 3, "Academic domain (heuristic)"
    return {"source_quality_score": score, "source_quality_label": label,
            "source_quality_note": "Domain/publisher heuristics only; not an endorsement or fact-check."}

def assess_relevance(title="", snippet="", industry="", problem_type="", manufacturing_focus=True):
    """Score workforce relevance and industry alignment with explainable keyword matches."""
    combined = " ".join(str(x or "") for x in (title, snippet, industry, problem_type))
    workforce_score = _term_score(combined, WORKFORCE_TERMS)
    manufacturing_score = _term_score(combined, MANUFACTURING_TERMS)
    if workforce_score >= 4:
        relevance_label = "Strong workforce relevance"
    elif workforce_score >= 2:
        relevance_label = "Possible workforce relevance"
    else:
        relevance_label = "Weak workforce relevance"
    manufacturing_label = ("Manufacturing-aligned" if manufacturing_score >= 3
                          else "Manufacturing context unclear" if manufacturing_score
                          else "Not manufacturing-specific")
    return {"workforce_relevance_score": workforce_score,
            "workforce_relevance_label": relevance_label,
            "manufacturing_relevance_score": manufacturing_score,
            "manufacturing_relevance_label": manufacturing_label,
            "manufacturing_focus_priority": bool(manufacturing_focus and manufacturing_score >= 3),
            "relevance_note": "Keyword triage only; review source text before accepting findings."}

def assess_geography(actual_geography=None, country_searched=None, title="", snippet=""):
    """Distinguish explicit geographic evidence from search targeting."""
    explicit = str(actual_geography or "").strip()
    searched = str(country_searched or "").strip()
    text = f"{title} {snippet}".casefold()
    if explicit and explicit.casefold() not in {"unknown", "not specified", "n/a"}:
        label, confidence = "Explicit geography supplied", "Explicit metadata"
    elif searched and searched.casefold() in text:
        label, confidence = "Search geography mentioned in source text", "Text mention; verify context"
    elif searched:
        label, confidence = "Search geography only", "Not confirmed"
    else:
        label, confidence = "Global / geography not established", "Not confirmed"
    return {"actual_geography": explicit or None, "country_searched": searched or None,
            "geography_label": label, "geography_validation": confidence,
            "geography_note": "Search location is not proof of the finding's geographic scope."}

def fingerprint_record(record):
    """Stable fingerprint using normalized URL first, then title+snippet fallback."""
    url = canonicalize_url(record.get("url") or record.get("source_url") or "")
    if url:
        basis = "url:" + url
    else:
        title = re.sub(r"\s+", " ", str(record.get("title") or "").casefold()).strip()
        snippet = re.sub(r"\s+", " ", str(record.get("snippet") or record.get("content") or "").casefold()).strip()
        basis = "text:" + title + "|" + snippet[:500]
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()

def deduplicate_sources(records):
    """Deduplicate normalized URLs, retaining merged metadata and all original URLs."""
    unique, index = [], {}
    for raw in records or []:
        item = dict(raw)
        canonical = canonicalize_url(item.get("url") or item.get("source_url") or "")
        key = "url:" + canonical if canonical else "fp:" + fingerprint_record(item)
        if key not in index:
            item["canonical_url"] = canonical or None
            item["duplicate_count"] = 1
            item["original_urls"] = [item.get("url") or item.get("source_url")] if (item.get("url") or item.get("source_url")) else []
            index[key] = len(unique)
            unique.append(item)
        else:
            existing = unique[index[key]]
            existing["duplicate_count"] += 1
            original = item.get("url") or item.get("source_url")
            if original and original not in existing["original_urls"]:
                existing["original_urls"].append(original)
            for field in ("snippet", "title", "publication_date", "publisher", "source_class"):
                if not existing.get(field) and item.get(field):
                    existing[field] = item[field]
    return unique

def evaluate_candidate(record, reference_date=None, manufacturing_focus=True):
    """Attach quality/relevance/recency/geography annotations to one candidate."""
    item = dict(record)
    quality = source_quality_assessment(item.get("url") or item.get("source_url", ""),
                                      item.get("title", ""), item.get("publisher", ""),
                                      item.get("source_class", ""))
    relevance = assess_relevance(item.get("title", ""), item.get("snippet") or item.get("content", ""),
                                item.get("industry", ""), item.get("problem_type", ""),
                                manufacturing_focus=manufacturing_focus)
    recency = recency_assessment(item.get("publication_date") or item.get("published_date") or item.get("search_published_date"), reference_date)
    geography = assess_geography(item.get("actual_geography") or item.get("country") or "",
                                item.get("country_searched"), item.get("title", ""), item.get("snippet") or item.get("content", ""))
    item.update(quality)
    item.update(relevance)
    item.update(recency)
    item.update(geography)
    return item

def evaluate_candidates(records, reference_date=None, manufacturing_focus=True):
    """Deduplicate first, then annotate candidates without destructive filtering."""
    return [evaluate_candidate(item, reference_date, manufacturing_focus)
            for item in deduplicate_sources(records)]
