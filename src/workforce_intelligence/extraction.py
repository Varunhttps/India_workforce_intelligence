"""Structured extraction interface; model output is always treated as unverified."""
from __future__ import annotations
import json
from typing import Any
from .records import FINDING_COLUMNS

EXTRACTION_FIELDS=("problem_type","description","country","region","industry","sub_industry","company","publication_date","data_period")
SYSTEM_PROMPT="""Identify explicitly reported workforce problems in the supplied source text. Focus on manufacturing when relevant, but retain other industries when the research mode permits them. Do not propose solutions or recommendations. Do not infer a country from the search query, source domain, or company headquarters: only populate country/region when the source text clearly states the geographic scope of the problem. Distinguish the country/region where a problem occurs from the country used to search. Return only JSON: {\\"findings\\":[{...}]}. Each finding must include problem_type and a concise description. Use null for unsupported fields. Do not add evidence, confidence, or HR category fields."""

def build_extraction_prompt(source_text,source_metadata):
    metadata={k:source_metadata.get(k) for k in ("title","url","industry","country_searched","search_published_date")}
    return SYSTEM_PROMPT+"\nSOURCE METADATA (not proof of geography):\n"+json.dumps(metadata,ensure_ascii=False)+"\nSOURCE TEXT:\n"+source_text[:100000]

def parse_extraction_response(response_text,source_metadata):
    raw=response_text.strip()
    if raw.startswith("```"):
        raw=raw.split("\n",1)[-1].rsplit("```",1)[0].strip()
    payload=json.loads(raw)
    rows=payload.get("findings",[]) if isinstance(payload,dict) else []
    output=[]
    for item in rows:
        if not isinstance(item,dict): continue
        row={k:item.get(k) for k in EXTRACTION_FIELDS}
        if not row.get("problem_type") or not row.get("description"): continue
        # Trusted metadata, never model-generated source attribution.
        row.update(source_name=source_metadata.get("title"),source_url=source_metadata.get("url"),review_status="Needs source verification")
        output.append(row)
    return output
