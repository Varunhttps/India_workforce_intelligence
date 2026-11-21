# Global Country Coverage Intelligence

The country coverage module aggregates research findings by their **explicit finding geography**. It does not use the country searched as a proxy for country coverage.

## Metrics
- Finding count
- Distinct industries
- Distinct source URLs
- Distinct workforce problem labels
- Manufacturing-aligned finding count (transparent keyword heuristic)
- Latest evidence date, when parseable
- Broad geographic region

## Functions
- `normalize_country(value)`: normalize common aliases and suppress unknown/global placeholders.
- `country_region(country)`: broad region mapping; unmapped countries are labeled `Other / unclassified`.
- `summarize_country_coverage(findings, target_countries=())`: sorted country summary; optional target countries show zero-coverage entries.
- `build_country_industry_matrix(findings, target_countries=())`: country-by-industry count matrix.

## Interpretation
Coverage metrics describe what the dataset explicitly attributes to countries. More findings do not imply greater workforce-problem severity. Manufacturing alignment is a keyword heuristic, not a verified sector classification. Countries outside the built-in region list remain visible and are not dropped. The optional target list is user-supplied, so zero-coverage gaps are only assessed against an explicit benchmark.
