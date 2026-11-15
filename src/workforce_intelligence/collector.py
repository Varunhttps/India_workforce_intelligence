"""Bounded source collection with URL, redirect, content-type and size safeguards."""
from __future__ import annotations
import hashlib
import ipaddress
import socket
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

try:
    import trafilatura
except ImportError:
    trafilatura = None
try:
    import pymupdf as fitz
except ImportError:
    fitz = None

USER_AGENT = "GlobalWorkforceIntelligence/0.2 (+public-source research)"
MAX_BYTES = 15 * 1024 * 1024
TIMEOUT = 30
MAX_REDIRECTS = 5
REDIRECT_CODES = {301, 302, 303, 307, 308}


def _safe_name(url):
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]


def _validate_public_url(url, resolver=socket.getaddrinfo):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only absolute HTTP(S) URLs are allowed.")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing credentials are not allowed.")
    host = parsed.hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        raise ValueError("Local hostnames are not allowed.")
    try:
        addresses = {ipaddress.ip_address(host)}
    except ValueError:
        try:
            addresses = {ipaddress.ip_address(item[4][0]) for item in resolver(host, None, type=socket.SOCK_STREAM)}
        except socket.gaierror as exc:
            raise ValueError("Could not resolve source hostname.") from exc
    if not addresses:
        raise ValueError("Source hostname did not resolve.")
    for address in addresses:
        if not address.is_global:
            raise ValueError("Private, local, reserved or non-public network addresses are not allowed.")
    return parsed


def _extract_pdf(data):
    if fitz is None:
        raise RuntimeError("Install PyMuPDF to extract PDF documents.")
    doc = fitz.open(stream=data, filetype="pdf")
    try:
        return "\n".join(f"[Page {i + 1}]\n{page.get_text()}" for i, page in enumerate(doc))
    finally:
        doc.close()


def _extract_html(data, url):
    html = data.decode("utf-8", errors="replace")
    if trafilatura:
        extracted = trafilatura.extract(html, url=url, include_comments=False, include_tables=True)
        if extracted and extracted.strip():
            return extracted.strip()
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "form"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)


def collect_document(url, output_dir, session=None, timeout=TIMEOUT, max_bytes=MAX_BYTES, max_redirects=MAX_REDIRECTS):
    current_url = url
    client = session or requests.Session()
    response = None
    for hop in range(max_redirects + 1):
        _validate_public_url(current_url)
        response = client.get(
            current_url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/pdf;q=0.9,*/*;q=0.1"},
            timeout=timeout,
            stream=True,
            allow_redirects=False,
        )
        if response.status_code not in REDIRECT_CODES:
            break
        location = response.headers.get("Location")
        response.close()
        if not location:
            raise ValueError("Redirect response did not include a Location header.")
        if hop >= max_redirects:
            raise ValueError("Source exceeded the maximum redirect count.")
        current_url = urljoin(current_url, location)
    if response is None:
        raise RuntimeError("Source request did not return a response.")

    with response:
        response.raise_for_status()
        final_url = response.url or current_url
        _validate_public_url(final_url)
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        declared = response.headers.get("Content-Length")
        if declared:
            try:
                if int(declared) > max_bytes:
                    raise ValueError("Document exceeds configured size limit.")
            except ValueError as exc:
                if "exceeds" in str(exc):
                    raise
        chunks, total = [], 0
        for chunk in response.iter_content(65536):
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                raise ValueError("Document exceeds configured size limit.")
            chunks.append(chunk)
        data = b"".join(chunks)
        is_pdf = content_type == "application/pdf" or urlparse(final_url).path.lower().endswith(".pdf") or data[:5] == b"%PDF-"
        if not is_pdf and content_type not in {"text/html", "application/xhtml+xml", ""}:
            raise ValueError(f"Unsupported source content type: {content_type or 'unknown'}")
        text = _extract_pdf(data) if is_pdf else _extract_html(data, final_url)
        if len(text.strip()) < 200:
            raise ValueError("Extracted text is too short to review reliably.")
        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)
        target = path / (_safe_name(url) + (".pdf.txt" if is_pdf else ".html.txt"))
        target.write_text(text, encoding="utf-8")
        return {
            "source_url": url, "final_url": final_url, "local_path": str(target),
            "content_type": content_type, "bytes_downloaded": total,
            "extracted_characters": len(text), "collection_status": "Collected",
        }
