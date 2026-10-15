"""Source adapters. Each adapter is a function (cfg: dict, ctx: Context) -> list[Mention]."""
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date

from ..classify import classify
from ..fetch import document_pages, scan_document
from ..matcher import Matcher
from ..models import Mention, Window

log = logging.getLogger(__name__)


@dataclass
class Context:
    window: Window               # press: the look-back period
    meeting_window: Window       # meetings: look-back period plus upcoming meetings
    matcher: Matcher
    exclude_meetings: list[re.Pattern]
    exclude_domains: list[str]
    packets: bool = False        # also scan full agenda packets / staff-report attachments
    use_cache: bool = True
    workers: int = 6
    # Extra keywords (keywords.txt) searched in upcoming meetings only: {phrase: Matcher}
    keywords: dict[str, Matcher] | None = None

    def is_upcoming(self, d: date) -> bool:
        return d > self.window.end

    def meeting_excluded(self, *names: str) -> bool:
        return any(p.search(n or "") for p in self.exclude_meetings for n in names)

    def domain_excluded(self, url: str) -> bool:
        host = re.sub(r"^https?://([^/]+).*", r"\1", url or "").lower()
        return any(host == d or host.endswith("." + d) for d in self.exclude_domains)


@dataclass
class MeetingDoc:
    meeting: str      # e.g. "Board of Supervisors"
    date: date
    url: str
    kind: str         # "Agenda", "Minutes", "Packet", "Staff report: ..."
    text: str = ""    # if set, scan this text instead of downloading url


def _scan_pages(pages: list[str], matcher: Matcher, max_snippets: int) -> tuple[int, list[str]]:
    """Hit count and page-labelled snippets ("p.12: ...") for already-extracted pages."""
    total, snippets = 0, []
    for i, text in enumerate(pages, 1):
        n, snips = matcher.find(text, max_snippets=max(0, max_snippets - len(snippets)))
        total += n
        snippets += [f"p.{i}: {s}" if len(pages) > 1 else s for s in snips]
    return total, snippets


def _combined(keywords: dict[str, Matcher], matched: dict) -> Matcher:
    """One matcher for the keywords a document matched (for classifying keyword-only hits)."""
    return Matcher([keywords[k].regex.pattern for k in matched])


# Per-source document counts for the app's "Sources checked" tab: {source: {"scanned", "unreadable"}}
SCAN_STATS: dict[str, dict[str, int]] = {}


def scan_meeting_docs(source: str, docs: list[MeetingDoc], ctx: Context) -> list[Mention]:
    """Filter docs to the window / exclusions, scan them in parallel, return hits."""
    seen, todo = set(), []
    for d in docs:
        key = d.url if not d.text else (d.url, d.kind)
        if key in seen or not ctx.meeting_window.contains(d.date) or ctx.meeting_excluded(d.meeting):
            continue
        seen.add(key)
        todo.append(d)
    log.info("%s: scanning %d meeting documents", source, len(todo))

    def work(d: MeetingDoc) -> tuple[Mention | None, bool]:
        if d.text:
            n, snips = ctx.matcher.find(d.text)
            note = ""
        else:
            n, snips, note = scan_document(d.url, ctx.matcher, ctx.use_cache)
        unreadable = note.startswith("unreadable") or note.startswith("no extractable")
        if unreadable:
            log.info("%s | %s %s: %s", source, d.meeting, d.date, note)
            return None, unreadable

        def pages() -> list[str]:
            return [d.text] if d.text else document_pages(d.url, ctx.use_cache)  # cached by the scan

        # Upcoming meetings are also searched for the extra keywords.
        keyword_hits = {}
        if ctx.keywords and ctx.is_upcoming(d.date):
            try:
                text_pages = pages()
                for phrase, km in ctx.keywords.items():
                    count, kw_snips = _scan_pages(text_pages, km, 3)
                    if count:
                        keyword_hits[phrase] = {"count": count, "snippets": kw_snips}
            except Exception as e:
                log.info("%s | %s: keyword search failed: %s", source, d.meeting, e)
        if not n and not keyword_hits:
            return None, unreadable

        # How the terms come up (agenda item, public comment, ...): judged from the TRPA
        # mentions, or from the keyword matches when TRPA isn't mentioned.
        try:
            basis = ctx.matcher if n else _combined(ctx.keywords, keyword_hits)
            contexts = classify(pages(), basis, "Agenda" if d.text else d.kind)
        except Exception as e:
            log.info("%s | %s: could not classify: %s", source, d.meeting, e)
            contexts = []
        return Mention("meeting", source, d.meeting, d.date, d.url, n, snips, d.kind,
                       contexts=contexts, keywords=keyword_hits), unreadable

    with ThreadPoolExecutor(ctx.workers) as pool:
        results = list(pool.map(work, todo))
    stats = SCAN_STATS.setdefault(source, {"scanned": 0, "unreadable": 0})
    stats["scanned"] += len(results)
    stats["unreadable"] += sum(u for _, u in results)
    return [m for m, _ in results if m]


def get_adapter(kind: str):
    from . import civicclerk, civicplus, custom, granicus, legistar, municode, news
    return {
        "civicclerk": civicclerk.run,
        "ntpud": custom.ntpud,
        "ttd": custom.ttd,
        "lahontan": custom.lahontan,
        "tahoe_conservancy": custom.tahoe_conservancy,
        "streamline": custom.streamline,
        "pdf_links": custom.pdf_links,
        "ntfire": custom.ntfire,
        "google_news": news.google_news,
        "bing_news": news.bing_news,
        "rss": news.rss,
        "legistar": legistar.run,
        "granicus": granicus.run,
        "municode": municode.run,
        "civicplus": civicplus.run,
    }[kind]
