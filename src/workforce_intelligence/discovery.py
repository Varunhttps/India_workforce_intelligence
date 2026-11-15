"""Tavily public-source discovery. Results are candidates, not verified sources."""
import os
from datetime import datetime,timezone
from urllib.parse import urlparse
import requests
TAVILY_URL="https://api.tavily.com/search"
TERMS='"workforce shortage" OR "labour shortage" OR "labor shortage" OR "skills gap" OR "skills shortage" OR "recruitment difficulties" OR "employee retention" OR "talent shortage"'
def classify_source_domain(domain):
    host = (domain or "").lower().split(":")[0].removeprefix("www.")
    if host.endswith(".gov") or ".gov." in host or host.endswith(".gov.uk") or host.endswith(".gov.in"):
        return "Government domain (heuristic)"
    if any(token in host for token in ("oecd.org", "ilo.org", "worldbank.org", "weforum.org", "europa.eu", "un.org")):
        return "Intergovernmental / multilateral (heuristic)"
    if host.endswith(".edu") or host.endswith(".ac.uk") or host.endswith(".ac.in"):
        return "Academic domain (heuristic)"
    if any(token in host for token in ("mckinsey.com", "deloitte.com", "pwc.com", "ey.com", "kpmg.com", "bcg.com")):
        return "Research / consulting publisher (heuristic)"
    if any(token in host for token in ("manufacturers", "industry", "association", "federation", "chamber")):
        return "Possible industry body (heuristic)"
    return "Other / unclassified"

def make_query(industry,country=None):
    geography=f" {country.strip()}" if country and country.strip() else " global"
    return f'{industry}{geography} workforce challenges {TERMS} report research data'
def discover_sources(industries,api_key=None,country=None,max_results=5,timeout=45,session=None):
    key=api_key or os.getenv("TAVILY_API_KEY")
    if not key: raise ValueError("Set TAVILY_API_KEY or pass api_key.")
    if not 1<=max_results<=20: raise ValueError("max_results must be between 1 and 20.")
    client=session or requests.Session(); found={}
    for industry in industries:
        query=make_query(industry,country)
        response=client.post(TAVILY_URL,json={"api_key":key,"query":query,"topic":"general","search_depth":"basic","max_results":max_results,"include_answer":False,"include_raw_content":False},timeout=timeout)
        response.raise_for_status()
        for item in response.json().get("results",[]):
            url=(item.get("url") or "").strip(); parsed=urlparse(url)
            if parsed.scheme not in {"http","https"} or not parsed.netloc: continue
            found.setdefault(url,{"industry":industry,"country_searched":country,"title":item.get("title"),"url":url,"domain":parsed.netloc.lower(),"source_class":classify_source_domain(parsed.netloc),"snippet":item.get("content"),"search_score":item.get("score"),"search_published_date":item.get("published_date"),"discovered_at":datetime.now(timezone.utc).isoformat(),"discovery_status":"Candidate - not verified"})
    priority = {"Government domain (heuristic)": 0, "Intergovernmental / multilateral (heuristic)": 1,
                "Academic domain (heuristic)": 2, "Research / consulting publisher (heuristic)": 3,
                "Possible industry body (heuristic)": 4, "Other / unclassified": 5}
    return sorted(found.values(), key=lambda item: (priority.get(item.get("source_class"), 9), -(item.get("search_score") or 0)))
