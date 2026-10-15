"""HTTP session, document download, text extraction and on-disk cache."""
import hashlib
import io
import json
import logging
import re
import threading
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from requests.adapters import HTTPAdapter, Retry

from .matcher import Matcher

log = logging.getLogger(__name__)

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/140.0 Safari/537.36 TRPA-mention-monitor")
MAX_DOC_BYTES = 80 * 1024 * 1024
CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"
CACHE_TTL_SECONDS = 24 * 3600

# Granicus serves attachments from a bucket whose name contains underscores, which
# fails TLS hostname checks in virtual-host style. Rewrite to path style.
_S3_VHOST = re.compile(r"^https?://([A-Za-z0-9_.-]*_[A-Za-z0-9_.-]*)\.s3\.amazonaws\.com/", re.I)


def make_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=4, backoff_factor=1.5, status_forcelist=[429, 500, 502, 503, 504],
                  allowed_methods=["GET", "POST"])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    s.headers["User-Agent"] = USER_AGENT
    return s


SESSION = make_session()


def _fix_url(url: str) -> str:
    return _S3_VHOST.sub(r"https://s3.amazonaws.com/\1/", url)


# Some hosts (South Tahoe PUD and Tahoe RCD share one) refuse Python's TLS handshake while
# letting browsers through. For those, fall back to curl_cffi, which connects like Chrome,
# and keep using it for that host for the rest of the run.
_BROWSER_HOSTS: set[str] = set()


class _BrowserResponse:
    """Just enough of requests.Response for get()/_download() callers."""
    def __init__(self, r):
        self.status_code, self.headers, self.content, self.url = r.status_code, r.headers, r.content, r.url
        self.encoding = r.encoding

    @property
    def text(self) -> str:
        return self.content.decode(self.encoding or "utf-8", errors="replace")

    def json(self):
        import json as _json
        return _json.loads(self.content)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} for url: {self.url}")

    def iter_content(self, size: int = 1 << 16):
        for i in range(0, len(self.content), size):
            yield self.content[i:i + size]


def _browser_get(url: str, timeout: int, params=None) -> "_BrowserResponse":
    from curl_cffi import requests as browser   # optional dependency
    # Neutral Accept, like the standard client: a browser-style "text/html" Accept makes some
    # APIs (Legistar) answer in XML instead of JSON.
    r = browser.get(url, params=params, impersonate="chrome", timeout=timeout, allow_redirects=True,
                    headers={"Accept": "*/*"})
    out = _BrowserResponse(r)
    out.raise_for_status()
    return out


class BlockedError(requests.RequestException):
    """The site answered with a bot-protection page instead of the content."""


# Bot-protection pages (Incapsula, Cloudflare) come back as small "successful" HTML pages;
# without this check they look like a page with no meetings on it.
_BLOCK_PAGE = re.compile(r"Incapsula incident ID|Request unsuccessful\. Incapsula|cf-chl-|"
                         r"<title>Just a moment\.\.\.</title>|Attention Required! \| Cloudflare")


def _check_blocked(r, url: str):
    ctype = r.headers.get("content-type", "") if r.headers else ""
    if "html" in ctype and len(r.content or b"") < 20000:
        if _BLOCK_PAGE.search(r.content.decode("utf-8", errors="replace")):
            raise BlockedError(f"blocked by the site's bot protection: {url}")
    return r


def get(url: str, timeout: int = 60, **kw) -> requests.Response:
    """GET that follows redirects manually so broken S3 hostnames can be rewritten."""
    url = _fix_url(url)
    host = urlparse(url).hostname or ""
    # Once several unrelated hosts refuse the standard client, the problem is this machine's
    # network rather than the sites, so skip the slow retries and go browser-like everywhere.
    if host in _BROWSER_HOSTS or len(_BROWSER_HOSTS) >= 3:
        return _check_blocked(_browser_get(url, timeout, kw.get("params")), url)
    try:
        for _ in range(10):
            r = SESSION.get(url, timeout=timeout, allow_redirects=False, **kw)
            if r.is_redirect and "Location" in r.headers:
                url = _fix_url(urljoin(url, r.headers["Location"]))
                continue
            r.raise_for_status()
            if "html" in r.headers.get("content-type", "") and not kw.get("stream"):
                _check_blocked(r, url)
            return r
        raise requests.TooManyRedirects(url)
    except (requests.exceptions.SSLError, requests.exceptions.ConnectionError, requests.HTTPError,
            BlockedError) as e:
        # A 403 is often bot-blocking by connection fingerprint too; other HTTP errors are real.
        if isinstance(e, requests.HTTPError) and getattr(e.response, "status_code", None) != 403:
            raise
        try:
            r = _browser_get(url, timeout, kw.get("params"))
        except ImportError:
            raise e
        _check_blocked(r, url)   # blocked for the browser-like client too: let the source fail
        log.info("%s refused the standard client; using a browser-like connection", host)
        _BROWSER_HOSTS.add(host)
        return r


# Some agency servers drop connections when several downloads hit them at once
# (South Tahoe PUD does), so limit concurrent downloads per host.
PER_HOST_DOWNLOADS = 2
_host_slots: dict[str, threading.BoundedSemaphore] = defaultdict(
    lambda: threading.BoundedSemaphore(PER_HOST_DOWNLOADS))
_host_slots_lock = threading.Lock()


def _download(url: str) -> tuple[bytes, str]:
    with _host_slots_lock:
        slot = _host_slots[urlparse(url).hostname or ""]
    with slot:
        r = get(url, timeout=120, stream=True)
        buf = io.BytesIO()
        for chunk in r.iter_content(1 << 16):
            buf.write(chunk)
            if buf.tell() > MAX_DOC_BYTES:
                raise ValueError(f"document larger than {MAX_DOC_BYTES // 2**20} MB")
        return buf.getvalue(), r.headers.get("content-type", "")


_SHARE_CLASS = re.compile(r"(^|[-_ ])(share|sharing|social)([-_ ]|$)", re.I)
_SHARE_TEXT = re.compile(r"(\b(Share|Tweet|Email|Print|Copy Link)\b( (on|via) (Facebook|Twitter|X|LinkedIn|"
                         r"WhatsApp|Email|SMS|Reddit|Pinterest)\b)?\s*){2,}")


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "aside", "form"]):
        tag.decompose()
    # Social share bars ("Share on Facebook Share on Twitter ...") leak into article text.
    for tag in soup.find_all(class_=_SHARE_CLASS):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    return _SHARE_TEXT.sub(" ", text)


def extract_pages(data: bytes, content_type: str) -> list[str]:
    if data[:5] == b"%PDF-" or "pdf" in content_type:
        reader = PdfReader(io.BytesIO(data))
        pages = []
        for p in reader.pages:
            try:
                pages.append(p.extract_text() or "")
            except Exception:  # a single bad page shouldn't sink the document
                pages.append("")
        return pages
    return [html_to_text(data.decode("utf-8", errors="replace"))]


def document_pages(url: str, use_cache: bool = True) -> list[str]:
    """Download a PDF/HTML document and return its text, one string per page."""
    CACHE_DIR.mkdir(exist_ok=True)
    path = CACHE_DIR / (hashlib.sha1(url.encode()).hexdigest() + ".json")
    if use_cache and path.exists() and time.time() - path.stat().st_mtime < CACHE_TTL_SECONDS:
        return json.loads(path.read_text(encoding="utf-8"))
    data, ctype = _download(url)
    pages = extract_pages(data, ctype)
    path.write_text(json.dumps(pages), encoding="utf-8")
    return pages


def scan_document(url: str, matcher: Matcher, use_cache: bool = True) -> tuple[int, list[str], str]:
    """Return (hit count, snippets labelled with page numbers, note)."""
    try:
        pages = document_pages(url, use_cache)
    except Exception as e:
        log.warning("could not read %s: %s", url, e)
        return 0, [], f"unreadable: {e}"
    total, snippets = 0, []
    multi = len(pages) > 1
    for i, text in enumerate(pages, 1):
        n, snips = matcher.find(text, max_snippets=5 - len(snippets) if len(snippets) < 5 else 0)
        total += n
        snippets += [f"p.{i}: {s}" if multi else s for s in snips]
    note = "" if any(p.strip() for p in pages) else "no extractable text (scanned PDF?)"
    return total, snippets, note
