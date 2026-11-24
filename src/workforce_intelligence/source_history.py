"""Persistent, append-only source register history."""
from __future__ import annotations

import json
from pathlib import Path
from datetime import date


def update_source_history(sources, history_path, observed_at=None, historical_findings=None):
    path = Path(history_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    today = observed_at or date.today().isoformat()
    records = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
                url = row.get("source_url")
                if url:
                    records[url] = row
            except (json.JSONDecodeError, TypeError):
                continue
    # Bootstrap from retained finding history if this source register is new.
    for old in historical_findings or []:
        url = old.get("source_url")
        if url and url not in records:
            records[url] = {
                "source_url": url,
                "source_title": old.get("source_name") or "Previously collected source",
                "source_platform": old.get("source_platform") or "Web",
                "industry": old.get("industry"),
                "publication_date": old.get("publication_date"),
                "first_found_date": old.get("first_seen") or today,
            }
    for source in sources or []:
        url = source.get("Source URL")
        if not url:
            continue
        prior = records.get(url, {})
        records[url] = {
            **prior,
            "source_url": url,
            "source_title": source.get("Source title") or prior.get("source_title"),
            "source_platform": source.get("Source platform") or prior.get("source_platform") or "Web",
            "industry": source.get("Industry searched") or prior.get("industry"),
            "publication_date": source.get("Publication date") or prior.get("publication_date"),
            # Keep the original first-discovered date; never refresh it on later runs.
            "first_found_date": prior.get("first_found_date") or today,
        }
    path.write_text(
        "".join(json.dumps(records[url], ensure_ascii=False, sort_keys=True) + "\n" for url in sorted(records)),
        encoding="utf-8",
    )
    return list(records.values())


def save_source_history(records, history_path):
    """Persist merged source-history records without changing their first-found dates."""
    path = Path(history_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    by_url = {}
    for record in records or []:
        url = record.get("source_url") or record.get("Source URL")
        if not url:
            continue
        normalized = dict(record)
        normalized["source_url"] = url
        normalized.pop("Source URL", None)
        by_url[url] = normalized
    path.write_text(
        "".join(json.dumps(by_url[url], ensure_ascii=False, sort_keys=True) + "\\n" for url in sorted(by_url)),
        encoding="utf-8",
    )
    return list(by_url.values())
