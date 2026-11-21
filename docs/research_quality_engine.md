# Research Quality & Deduplication Engine

The `source_quality` module adds transparent, deterministic triage annotations. It is intentionally non-destructive: candidates are scored and labeled, not silently dropped.

## API
- `canonicalize_url(url)`: removes fragments, common tracking query parameters, normalizes host/path.
- `deduplicate_sources(records)`: deduplicates canonical URLs, falls back to stable title/snippet fingerprint, and retains duplicate counts and original URLs.
- `source_quality_assessment(...)`: domain/publisher heuristic quality tier. Never treats the tier as a fact-check.
- `assess_relevance(...)`: keyword scoring for workforce relevance and manufacturing alignment.
- `recency_assessment(publication_date, reference_date)`: transparent age bands; unknown dates stay unknown.
- `assess_geography(...)`: distinguishes explicit geography from search-target geography.
- `evaluate_candidate(record, ...)` / `evaluate_candidates(records, ...)`: annotate candidate(s) with all assessments.

## Manufacturing-aware behavior
Manufacturing terms include factories, production, assembly, industrial, machinery, automotive, semiconductor, electronics, metals, steel, chemicals, pharmaceuticals, food processing, textiles and aerospace. The manufacturing flag is a prioritization signal, not an exclusion: healthcare, logistics, retail, and other industries remain assessable.

## Caveats
All labels are heuristics and require review. Domain reputation cannot validate an article; keyword scores can miss context; source date fields may be ambiguous; search country does not establish where a reported issue occurs. This milestone does not wire automatic rejection into the production pipeline.
