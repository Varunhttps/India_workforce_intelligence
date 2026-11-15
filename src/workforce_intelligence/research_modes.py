"""Global research modes; manufacturing is the default."""
from dataclasses import dataclass
MANUFACTURING = ("Automotive manufacturing","Electronics manufacturing","Semiconductor manufacturing","Machinery and equipment manufacturing","Chemicals manufacturing","Pharmaceutical manufacturing","Food and beverage manufacturing","Textiles and apparel manufacturing","Metals and materials manufacturing","Aerospace manufacturing")
OTHER = ("Construction","Healthcare","Information technology","Logistics","Retail","Hospitality","Education","Energy","Agriculture","Banking and financial services")
@dataclass(frozen=True)
class ResearchPlan:
    mode: str
    industries: tuple[str,...]
def build_research_plan(mode="manufacturing", additional_industries=()):
    key=(mode or "manufacturing").strip().lower().replace("-","_").replace(" ","_")
    extra=tuple(x.strip() for x in additional_industries if x and x.strip())
    if key in {"manufacturing","manufacturing_research","default"}: label, items="manufacturing",MANUFACTURING
    elif key in {"other","other_industries","explore_other_industries"}: label,items="other_industries",OTHER+extra
    elif key in {"all","all_industries"}: label,items="all_industries",MANUFACTURING+OTHER+extra
    else: raise ValueError("mode must be manufacturing, other_industries, or all_industries")
    return ResearchPlan(label,tuple(dict.fromkeys(items)))
