"""Bounded source collection with URL, redirect, content-type and size safeguards."""
from __future__ import annotations
import hashlib
import ipaddress
import socket
import sys
import threading
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import ProxyError as RequestsProxyError
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.exceptions import ConnectTimeoutError, NameResolutionError, NewConnectionError
from urllib3.util import connection
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


def _resolve_public_addresses(host, resolver=socket.getaddrinfo):
    """Resolve a host and reject it if any answer is not a public IP address."""
    try:
        addresses = {ipaddress.ip_address(host)}
    except ValueError:
        try:
            addresses = {
                ipaddress.ip_address(item[4][0])
                for item in resolver(host, None, type=socket.SOCK_STREAM)
            }
        except socket.gaierror as exc:
            raise ValueError("Could not resolve source hostname.") from exc
    if not addresses:
        raise ValueError("Source hostname did not resolve.")
    for address in addresses:
        if not address.is_global:
            raise ValueError("Private, local, reserved or non-public network addresses are not allowed.")
    return addresses


def _validate_public_url(url, resolver=socket.getaddrinfo):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only absolute HTTP(S) URLs are allowed.")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing credentials are not allowed.")
    host = parsed.hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        raise ValueError("Local hostnames are not allowed.")
    _resolve_public_addresses(host, resolver=resolver)
    return parsed


class _PinnedConnectionMixin:
    """Connect to the already-validated IP while retaining the original host for TLS."""
    def __init__(self, *args, pinned_ip, **kwargs):
        self.pinned_ip = str(ipaddress.ip_address(pinned_ip))
        super().__init__(*args, **kwargs)

    def _new_conn(self):
        try:
            sock = connection.create_connection(
                (self.pinned_ip, self.port),
                self.timeout,
                source_address=self.source_address,
                socket_options=self.socket_options,
            )
        except socket.gaierror as exc:
            raise NameResolutionError(self.host, self, exc) from exc
        except TimeoutError as exc:
            raise ConnectTimeoutError(
                self, f"Connection to {self.host} timed out. (connect timeout={self.timeout})"
            ) from exc
        except OSError as exc:
            raise NewConnectionError(self, f"Failed to establish a pinned connection: {exc}") from exc
        sys.audit("http.client.connect", self, self.host, self.port)
        return sock


class _PinnedHTTPConnection(_PinnedConnectionMixin, HTTPConnection):
    pass


class _PinnedHTTPSConnection(_PinnedConnectionMixin, HTTPSConnection):
    pass


class _PinnedHTTPConnectionPool(HTTPConnectionPool):
    ConnectionCls = _PinnedHTTPConnection


class _PinnedHTTPSConnectionPool(HTTPSConnectionPool):
    ConnectionCls = _PinnedHTTPSConnection


class _PinnedIPAdapter(HTTPAdapter):
    """Requests adapter that validates DNS answers and connects to one pinned IP."""
    def __init__(self, resolver=socket.getaddrinfo, *args, **kwargs):
        self._resolver = resolver
        self._pinned_pools = {}
        self._pinned_pools_lock = threading.Lock()
        super().__init__(*args, **kwargs)

    def _get_pinned_pool(self, url, proxies=None):
        if proxies and any(proxies.values()):
            raise RequestsProxyError("Proxy use is disabled for public-source collection.")
        parsed = _validate_public_url(url, resolver=self._resolver)
        host = parsed.hostname.rstrip(".").lower()
        # Resolve again for the connection choice, validating this exact answer set.
        # The chosen address is passed to the socket connection, so it cannot be
        # replaced by a later DNS answer during connect().
        addresses = _resolve_public_addresses(host, resolver=self._resolver)
        pinned_ip = sorted(addresses, key=lambda ip: (ip.version, int(ip)))[0].compressed
        scheme = parsed.scheme.lower()
        port = parsed.port or (443 if scheme == "https" else 80)
        key = (scheme, host, port, pinned_ip)
        with self._pinned_pools_lock:
            pool = self._pinned_pools.get(key)
            if pool is None:
                pool_class = _PinnedHTTPSConnectionPool if scheme == "https" else _PinnedHTTPConnectionPool
                pool = pool_class(
                    host=host,
                    port=port,
                    pinned_ip=pinned_ip,
                    maxsize=self._pool_maxsize,
                    block=self._pool_block,
                )
                self._pinned_pools[key] = pool
        return pool

    # Requests 2.31 and 2.32+ call different adapter hooks; override both.
    def get_connection(self, url, proxies=None):
        return self._get_pinned_pool(url, proxies)

    def get_connection_with_tls_context(self, request, verify, proxies=None, cert=None):
        return self._get_pinned_pool(request.url, proxies)

    def close(self):
        with self._pinned_pools_lock:
            pools = list(self._pinned_pools.values())
            self._pinned_pools.clear()
        for pool in pools:
            pool.close()
        super().close()


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
    owns_client = session is None
    client = session or requests.Session()
    if not isinstance(client, requests.Session):
        raise TypeError("Custom collector sessions must be requests.Session instances so IP pinning can be enforced.")
    client.trust_env = False
    pinned_adapter = getattr(client, "_gwi_pinned_ip_adapter", None)
    if not isinstance(pinned_adapter, _PinnedIPAdapter):
        pinned_adapter = _PinnedIPAdapter()
        client._gwi_pinned_ip_adapter = pinned_adapter
        client.mount("http://", pinned_adapter)
        client.mount("https://", pinned_adapter)
    response = None
    try:
        for hop in range(max_redirects + 1):
            if client.get_adapter(current_url) is not pinned_adapter:
                raise ValueError("Custom session adapter bypasses DNS-pinned collection.")
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
    finally:
        if owns_client:
            client.close()
