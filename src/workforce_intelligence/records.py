"""Workbook schema, normalization and duplicate removal."""
from urllib.parse import urlparse
FINDING_COLUMNS=["problem_type","description","country","region","industry","sub_industry","company","source_name","source_url","publication_date","data_period","review_status"]
SOURCE_COLUMNS=["Source title","Source URL","Industry searched","Country searched","Actual geographic scope","Region","Publication date","Collection status","Relevance status","Verification status","Review notes"]
def valid_http_url(value):
    if not isinstance(value,str): return False
    p=urlparse(value.strip()); return p.scheme in {"http","https"} and bool(p.netloc)
def normalize_finding(item):
    row={c:item.get(c) for c in FINDING_COLUMNS}
    for k in ("problem_type","description","industry","source_name"):
        if row[k] is not None: row[k]=str(row[k]).strip() or None
    if row["source_url"] and not valid_http_url(row["source_url"]): raise ValueError("source_url must be a valid HTTP(S) URL")
    for k in ("country","region"):
        if row[k] in {"Not specified","Unknown",""}: row[k]=None
    return row
def deduplicate_findings(items):
    seen=set(); result=[]
    for raw in items:
        row=normalize_finding(raw); key=tuple(str(row.get(k) or "").strip().casefold() for k in ("problem_type","country","source_url","description"))
        if key not in seen: seen.add(key); result.append(row)
    return result
