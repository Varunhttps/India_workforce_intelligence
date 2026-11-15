"""Research-mode definitions and query planning."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

MANUFACTURING_INDUSTRIES = (
    "Automotive manufacturing", "Electronics manufacturing",
    "Semiconductor manufacturing", "Machinery and equipment manufacturing",
    "Chemicals manufacturing", "Pharmaceutical manufacturing",
    "Food and beverage manufacturing", "Textiles and apparel manufacturing",
    "Metals and materials manufacturing", "Aerospace manufacturing",
)
OTHER_INDUSTRIES = (
    "Construction", "Healthcare", "Information technology", "Logistics",
    "Retail", "Hospitality", "Education", "Energy", "Agriculture",
    "Banking and financial services",
)

@dataclass(frozen=True)
class ResearchPlan:
    mode: str
    industries: tuple[str, ...]


def build_research_plan(mode: str, additional_industries: Iterable[str] = ()) -> ResearchPlan:
    """Build a deterministic plan; manufacturing is the default focus."""
    normalized = (mode or "manufacturing").strip().lower().replace("-", "_").replace(" ", "_")
    extra = tuple(dict.fromkeys(x.strip() for x in additional_industries if x and x.strip()))
    if normalized in {"manufacturing", "manufacturing_research", "default"}:
        industries = MANUFACTURING_INDUSTRIES
        label = "manufacturing"
    elif normalized in {"other", "other_industries", "explore_other_industries"}:
        industries = OTHER_INDUSTRIES + extra
        label = "other_industries"
    elif normalized in {"all", "all_industries"}:
        industries = MANUFACTURING_INDUSTRIES + OTHER_INDUSTRIES + extra
        label = "all_industries"
    else:
        raise ValueError("mode must be manufacturing, other_industries, or all_industries")
    return ResearchPlan(label, tuple(dict.fromkeys(industries)))
