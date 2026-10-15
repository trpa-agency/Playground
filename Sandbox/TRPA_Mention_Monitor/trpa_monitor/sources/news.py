"""Press sources: Google News search, Bing News search and plain RSS/Atom feeds."""
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qs, urlparse

from ..fetch import get, html_to_text, scan_document
from ..models import Mention
from . import Context

log = logging.getLogger(__name__)
NS = {"content": "http://purl.org/rss/1.0/modules/content/",
      "atom": "http://www.w3.org/2005/Atom",
      "news": "https://www.bing.com/news/search"}


def _date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return parsedate_to_datetime(s).date()
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _items(xml: bytes) -> list[dict]:
    """Normalise RSS 2.0 and Atom entries to dicts."""
    root = ET.fromstring(xml)
    out = []
    for it in root.iter("item"):
        src = it.find("source")
        out.append({
            "title": (it.findtext("title") or "").strip(),
            "link": (it.findtext("link") or "").strip(),
            "date": _date(it.findtext("pubDate")),
            "summary": it.findtext("description") or "",
            "content": it.findtext("content:encoded", namespaces=NS) or "",
            "source": (src.text if src is not None else None) or it.findtext("{*}Source") or "",
            "source_url": src.get("url", "") if src is not None else "",
        })
    for it in root.iter(f"{{{NS['atom']}}}entry"):
        link = it.find("atom:link", NS)
        out.append({
            "title": (it.findtext("atom:title", "", NS)).strip(),
            "link": link.get("href", "") if link is not None else "",
            "date": _date(it.findtext("atom:published", None, NS) or it.findtext("atom:updated", None, NS)),
            "summary": it.findtext("atom:summary", "", NS),
            "content": it.findtext("atom:content", "", NS),
            "source": "", "source_url": "",
        })
    return out


def google_news(cfg: dict, ctx: Context) -> list[Mention]:
    before = ctx.window.end + timedelta(days=1)  # Google's before: is exclusive
    found = []
    for q in cfg["queries"]:
        xml = get("https://news.google.com/rss/search", params={
            "q": f"{q} after:{ctx.window.start:%Y-%m-%d} before:{before:%Y-%m-%d}",
            "hl": "en-US", "gl": "US", "ceid": "US:en"}).content
        for it in _items(xml):
            if not ctx.window.contains(it["date"]) or ctx.domain_excluded(it["source_url"]):
                continue
            # Google wraps links in an opaque redirect, so the article text can't be checked;
            # the headline is the best snippet available.
            title = re.sub(r"\s+-\s+[^-]+$", "", it["title"])
            n, snips = ctx.matcher.find(it["title"])
            found.append(Mention("press", cfg["name"], title, it["date"], it["link"],
                                 n, snips or [it["title"]], it["source"], verified=bool(n)))
    return found


def bing_news(cfg: dict, ctx: Context) -> list[Mention]:
    found = []
    for q in cfg["queries"]:
        xml = get("https://www.bing.com/news/search",
                  params={"q": q, "format": "rss", "qft": 'interval="9"'}).content  # 9 = past month
        for it in _items(xml):
            if not ctx.window.contains(it["date"]):
                continue
            url = parse_qs(urlparse(it["link"]).query).get("url", [it["link"]])[0]
            if ctx.domain_excluded(url):
                continue
            # Confirm against the article itself; many outlets render with JS or block
            # scrapers, so a miss is kept but marked unverified rather than dropped.
            n, snips, _ = scan_document(url, ctx.matcher, ctx.use_cache)
            found.append(Mention("press", cfg["name"], it["title"], it["date"], url, n,
                                 snips or [it["summary"] or it["title"]], it["source"],
                                 verified=bool(n)))
    return found


def _feed(url: str) -> bytes:
    """Fetch a feed. Some servers (Tahoe Weekly's) answer an ordinary request with an empty
    "304 Not Modified"; a cache-busting parameter gets the real feed."""
    r = get(url)
    if r.status_code == 304 or not r.content.strip():
        r = get(url, params={"nocache": int(time.time())})
    return r.content


def rss(cfg: dict, ctx: Context) -> list[Mention]:
    found = []
    for it in _items(_feed(cfg["url"])):
        if not ctx.window.contains(it["date"]) or ctx.domain_excluded(it["link"]):
            continue
        body = html_to_text(it["content"] or it["summary"])
        n, snips = ctx.matcher.find(it["title"] + "\n" + body)
        if not n and len(body) < 1500 and it["link"]:
            # Feed only carries an excerpt: check the full article.
            n, snips, _ = scan_document(it["link"], ctx.matcher, ctx.use_cache)
        if n:
            found.append(Mention("press", cfg["name"], it["title"], it["date"], it["link"],
                                 n, snips, cfg["name"]))
    return found
