"""Bounded, defensive HTML/PDF document collection."""
from __future__ import annotations
import hashlib
from pathlib import Path
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
try:
 import trafilatura
except ImportError:
 trafilatura=None
try:
 import fitz
except ImportError:
 fitz=None
USER_AGENT="GlobalWorkforceIntelligence/0.1 (+public-source research)"
MAX_BYTES=15*1024*1024
TIMEOUT=30

def _safe_name(url): return hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
def _extract_pdf(data):
 if fitz is None: raise RuntimeError("Install PyMuPDF to extract PDF documents.")
 doc=fitz.open(stream=data,filetype="pdf")
 try: return "\n".join(f"[Page {i+1}]\n{page.get_text()}" for i,page in enumerate(doc))
 finally: doc.close()
def _extract_html(data,url):
 html=data.decode("utf-8",errors="replace")
 if trafilatura:
  extracted=trafilatura.extract(html,url=url,include_comments=False,include_tables=True)
  if extracted and extracted.strip(): return extracted.strip()
 soup=BeautifulSoup(html,"html.parser")
 for tag in soup(["script","style","nav","footer","header","noscript"]): tag.decompose()
 return soup.get_text("\n",strip=True)
def collect_document(url,output_dir,session=None,timeout=TIMEOUT,max_bytes=MAX_BYTES):
 parsed=urlparse(url)
 if parsed.scheme not in {"http","https"} or not parsed.hostname: raise ValueError("Only absolute HTTP(S) URLs are allowed.")
 client=session or requests.Session()
 with client.get(url,headers={"User-Agent":USER_AGENT},timeout=timeout,stream=True,allow_redirects=True) as response:
  response.raise_for_status()
  final=urlparse(response.url)
  if final.scheme not in {"http","https"} or not final.hostname: raise ValueError("Unsafe redirect target.")
  declared=response.headers.get("Content-Length")
  if declared and int(declared)>max_bytes: raise ValueError("Document exceeds configured size limit.")
  chunks=[]; total=0
  for chunk in response.iter_content(65536):
   if not chunk: continue
   total+=len(chunk)
   if total>max_bytes: raise ValueError("Document exceeds configured size limit.")
   chunks.append(chunk)
  data=b"".join(chunks)
  content_type=response.headers.get("Content-Type","").lower()
  is_pdf="pdf" in content_type or final.path.lower().endswith(".pdf") or data[:5]==b"%PDF-"
  text=_extract_pdf(data) if is_pdf else _extract_html(data,response.url)
  if len(text.strip())<200: raise ValueError("Extracted text is too short to review reliably.")
  path=Path(output_dir); path.mkdir(parents=True,exist_ok=True)
  target=path/(_safe_name(url)+(".pdf.txt" if is_pdf else ".html.txt"))
  target.write_text(text,encoding="utf-8")
  return {"source_url":url,"final_url":response.url,"local_path":str(target),"content_type":content_type,"bytes_downloaded":total,"extracted_characters":len(text),"collection_status":"Collected"}
