"""Structured extraction with conservative industry and geography validation."""
from __future__ import annotations
import json
import re
from typing import Any

EXTRACTION_FIELDS = ("problem_type", "description", "country", "region", "industry", "sub_industry", "company", "publication_date", "data_period")

SYSTEM_PROMPT = """Identify only explicitly reported workforce problems in the supplied source text. Do not propose solutions or recommendations.
INDUSTRY RULES:
- The target industry is a search lead, NOT proof that every problem in the source belongs to that industry.
- Keep a finding only when its description and the source text explicitly connect the workforce problem to the target industry or to manufacturing generally.
- Do not include unrelated industries mentioned in passing (for example healthcare vacancies in a broad talent-shortage article when researching manufacturing).
- Set industry to the narrowest sector explicitly supported by the source. Never copy the target industry merely because it was used in the search.
GEOGRAPHY RULES:
- Do not infer a country from the search query, source domain, company headquarters, or an example.
- Populate country/region only when the source explicitly connects the problem to that geography. Use Global only when the source explicitly describes a global problem.
- Return null for unsupported fields.
Return only JSON in this shape: {"findings":[{"problem_type":"...","description":"...","industry":"...","country":null,"region":null,"sub_industry":null,"company":null,"publication_date":null,"data_period":null}]}. Each finding needs problem_type and a concise description. Do not add evidence, confidence, or HR category fields."""

_COUNTRY_ALIASES = {
    "united states": ("united states", "u.s.", "u.s.a.", "usa", "american"),
    "united kingdom": ("united kingdom", "u.k.", "uk", "britain", "british"),
    "south korea": ("south korea", "republic of korea", "korean"),
    "russia": ("russia", "russian federation"),
    "uae": ("uae", "united arab emirates"),
}

def _mentioned(value: str, source_text: str) -> bool:
    value = str(value or "").strip()
    if not value:
        return False
    low = source_text.casefold()
    aliases = _COUNTRY_ALIASES.get(value.casefold(), (value.casefold(),))
    return any(re.search(r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])", low) for alias in aliases)

def _industry_relevant(item: dict, target: str, source_text: str) -> bool:
    target_low = (target or "").casefold()
    declared = str(item.get("industry") or "").strip()
    description = str(item.get("description") or "").casefold()
    combined = (source_text + " " + description).casefold()

    # Explicitly unrelated sectors are not allowed through a manufacturing search.
    unrelated = ("healthcare", "hospital", "nursing", "education", "school", "retail", "hospitality", "banking", "financial services", "construction", "agriculture", "farming")
    if any(term in declared.casefold() for term in unrelated):
        return False

    if "manufactur" in target_low:
        manufacturing_terms = ("manufactur", "factory", "factories", "production line", "production worker", "industrial plant", "assembly plant", "semiconductor fab", "foundry")
        target_terms = {
            "automotive": ("automotive", "automobile", "vehicle", "car maker", "auto parts"),
            "electronics": ("electronics", "electronic components", "circuit board"),
            "semiconductor": ("semiconductor", "chipmaker", "chip manufacturing", "wafer fab", "foundry"),
            "machinery": ("machinery", "machine tool", "industrial equipment"),
            "chemical": ("chemical", "petrochemical"),
            "pharmaceutical": ("pharma", "pharmaceutical", "drug manufacturing"),
            "food": ("food processing", "food and beverage", "food manufacturing", "beverage manufacturing"),
            "textile": ("textile", "apparel", "garment"),
            "metal": ("metals", "steelmaking", "metal fabrication", "aluminium", "aluminum"),
            "aerospace": ("aerospace", "aircraft manufacturing", "aviation manufacturing"),
        }
        specific = next((terms for key, terms in target_terms.items() if key in target_low), ())
        explicit_target = any(term in combined for term in specific)
        generic_manufacturing = any(term in combined for term in manufacturing_terms)
        return explicit_target or generic_manufacturing

    # Other-industry mode: require the requested sector to be mentioned in the source/finding.
    sector = target_low.replace("&", "and")
    aliases = [sector]
    if sector == "information technology":
        aliases += ["information technology", "software", "it services"]
    if sector == "banking and financial services":
        aliases += ["banking", "financial services", "financial sector"]
    return any(term in combined for term in aliases)

def build_extraction_prompt(source_text, source_metadata):
    metadata = {k: source_metadata.get(k) for k in ("title", "url", "industry", "country_searched", "search_published_date")}
    return SYSTEM_PROMPT + "\nTARGET INDUSTRY (search lead only):\n" + str(source_metadata.get("industry") or "Not specified") + "\nSOURCE METADATA (not proof of geography):\n" + json.dumps(metadata, ensure_ascii=False) + "\nSOURCE TEXT:\n" + source_text[:100000]

def parse_extraction_response(response_text, source_metadata, source_text=""):
    raw = (response_text or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    payload = json.loads(raw)
    rows = payload.get("findings", []) if isinstance(payload, dict) else []
    output = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        row = {k: item.get(k) for k in EXTRACTION_FIELDS}
        if not row.get("problem_type") or not row.get("description"):
            continue
        target_industry = source_metadata.get("industry", "")
        if not _industry_relevant(row, target_industry, source_text):
            continue
        # Do not label a broad manufacturing claim as a specific manufacturing sub-sector.
        if "manufactur" in str(target_industry).casefold():
            target_low = str(target_industry).casefold()
            combined = (source_text + " " + str(row.get("description") or "")).casefold()
            specific_terms = {
                "automotive": ("automotive", "automobile", "vehicle", "car maker", "auto parts"),
                "electronics": ("electronics", "electronic components", "circuit board"),
                "semiconductor": ("semiconductor", "chipmaker", "chip manufacturing", "wafer fab", "foundry"),
                "machinery": ("machinery", "machine tool", "industrial equipment"),
                "chemical": ("chemical", "petrochemical"),
                "pharmaceutical": ("pharma", "pharmaceutical", "drug manufacturing"),
                "food": ("food processing", "food and beverage", "food manufacturing", "beverage manufacturing"),
                "textile": ("textile", "apparel", "garment"),
                "metal": ("metals", "steelmaking", "metal fabrication", "aluminium", "aluminum"),
                "aerospace": ("aerospace", "aircraft manufacturing", "aviation manufacturing"),
            }
            specific = next((terms for key, terms in specific_terms.items() if key in target_low), ())
            if specific and not any(term in combined for term in specific):
                row["industry"] = "Manufacturing"
            elif not row.get("industry"):
                row["industry"] = target_industry
        # Geography must be explicitly present in the source text, not inferred by the model.
        for field in ("country", "region"):
            value = row.get(field)
            if value and str(value).casefold() not in {"global", "worldwide"} and not _mentioned(str(value), source_text):
                row[field] = None
        if row.get("region") and str(row["region"]).casefold() in {"global", "worldwide"} and not re.search(r"\b(global|worldwide|across the world)\b", source_text, re.I):
            row["region"] = None
        # Never let model output alter source attribution.
        row.update(source_name=source_metadata.get("title"), source_url=source_metadata.get("url"), review_status="Needs source verification")
        output.append(row)
    return output
