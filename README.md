# Global Workforce Intelligence

A public-source research pipeline to identify and classify workforce problems globally. Manufacturing is the primary focus, while other industries remain explorable. The agent identifies reported problems; it does not generate solutions.

## Research modes
- **Manufacturing Research** (default): automotive, electronics, semiconductors, machinery, chemicals, pharmaceuticals, food and beverage, textiles, metals and aerospace manufacturing.
- **Explore Other Industries**: construction, healthcare, IT, logistics, retail, hospitality, education, energy, agriculture and financial services.
- **All Industries**: both groups.

## Initial modular foundation
- `research_modes.py`: mode selection and industry scope.
- `discovery.py`: Tavily source discovery with global queries.
- `records.py`: workbook schema, URL checks and deduplication.
- `reporting.py`: Excel export (findings, source register, research summary).

## Setup
Python 3.10+ recommended.

```bash
pip install -r requirements.txt
export TAVILY_API_KEY="your-key"
PYTHONPATH=src python -m unittest discover -s tests -v
```

Discovery records are candidates, not verified findings. Search geography and actual source geography are separate: never infer a finding's country from the search query. Verify publication date, geographic scope, industry relevance and problem statement against the original source.

## Manager workbook
The findings sheet includes problem type, description, country, region, industry, sub-industry, company, source name, source URL, publication date, data period and review status. Evidence, Confidence and HR Category columns are intentionally excluded.

## Status
This is the first modular foundation, not a completed end-to-end pipeline. Document collection, model-based extraction, source-level verification and Colab integration are still to be ported and tested.
