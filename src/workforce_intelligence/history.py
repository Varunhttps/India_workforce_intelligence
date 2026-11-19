"""Append-only, deduplicated finding history with week-level tracking."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def finding_key(row):
    parts = (_clean(row.get("problem_type")), _clean(row.get("description")),
             _clean(row.get("country")), _clean(row.get("industry")),
             _clean(row.get("source_url")))
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def week_start(value):
    """Return the ISO Monday date for an ISO YYYY-MM-DD date."""
    day = date.fromisoformat(str(value)[:10])
    return (day - timedelta(days=day.weekday())).isoformat()


def update_history(findings, history_path, observed_at=None):
    path = Path(history_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    observed = observed_at or datetime.now(timezone.utc).date().isoformat()
    current_week = week_start(observed)
    existing = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
                if item.get("finding_key"):
                    first = item.get("first_seen") or observed
                    last = item.get("last_seen") or first
                    item.setdefault("first_seen_week", week_start(first))
                    item.setdefault("last_seen_week", week_start(last))
                    item.setdefault("weeks_seen", sorted({item["first_seen_week"], item["last_seen_week"]}))
                    existing[item["finding_key"]] = item
            except (json.JSONDecodeError, ValueError):
                continue

    new_findings, recurring_findings = [], []
    seen_this_run = set()
    for finding in findings:
        key = finding_key(finding)
        if key in seen_this_run:
            continue
        seen_this_run.add(key)
        prior = existing.get(key)
        if prior:
            prior["last_seen"] = observed
            prior["last_seen_week"] = current_week
            prior["occurrences"] = int(prior.get("occurrences", 1)) + 1
            prior["weeks_seen"] = sorted(set(prior.get("weeks_seen", [])) | {current_week})
            prior["latest_description"] = finding.get("description")
            prior["latest_source_name"] = finding.get("source_name")
            prior["latest_source_url"] = finding.get("source_url")
            recurring_findings.append({**finding, "history_status": "Recurring",
                                       "weekly_status": "New this week" if prior["first_seen_week"] == current_week else "Recurring this week",
                                       "first_seen": prior["first_seen"], "last_seen": observed,
                                       "first_seen_week": prior["first_seen_week"],
                                       "last_seen_week": current_week,
                                       "weeks_seen": prior["weeks_seen"],
                                       "occurrences": prior["occurrences"]})
        else:
            item = {"finding_key": key, "first_seen": observed, "last_seen": observed,
                    "first_seen_week": current_week, "last_seen_week": current_week,
                    "weeks_seen": [current_week], "occurrences": 1,
                    "problem_type": finding.get("problem_type"),
                    "description": finding.get("description"), "country": finding.get("country"),
                    "region": finding.get("region"), "industry": finding.get("industry"),
                    "source_name": finding.get("source_name"), "source_url": finding.get("source_url"),
                    "source_platform": finding.get("source_platform")}
            existing[key] = item
            new_findings.append({**finding, "history_status": "New",
                                 "weekly_status": "New this week",
                                 "first_seen": observed, "last_seen": observed,
                                 "first_seen_week": current_week, "last_seen_week": current_week,
                                 "weeks_seen": [current_week], "occurrences": 1})

    # Missing from this run does not mean resolved; retain the original last_seen date.
    content = "".join(json.dumps(existing[key], ensure_ascii=False, sort_keys=True) + "\n"
                      for key in sorted(existing))
    path.write_text(content, encoding="utf-8")
    return {"new": new_findings, "recurring": recurring_findings,
            "history_records": len(existing), "history_path": str(path),
            "week_start": current_week}
