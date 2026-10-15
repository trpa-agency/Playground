"""Scrapers for agencies that publish meetings on their own websites."""
import logging
import re
from datetime import timedelta
from urllib.parse import unquote, urljoin

from bs4 import BeautifulSoup

from ..dates import parse_date
from ..fetch import get, html_to_text
from . import Context, MeetingDoc, scan_meeting_docs

log = logging.getLogger(__name__)


def _soup(url: str) -> tuple[BeautifulSoup, str]:
    r = get(url, timeout=90)
    return BeautifulSoup(r.text, "html.parser"), r.url


def _filename(url: str) -> str:
    return unquote(url.rstrip("/").rsplit("/", 1)[-1])


# --------------------------------------------------------------------------- NTPUD
def ntpud(cfg: dict, ctx: Context):
    """North Tahoe PUD: paged list of Agenda/Packet links; the date is in each file name
    (e.g. 10132026-Regular-Board-Meeting-Agenda.pdf)."""
    base = cfg.get("url", "https://ntpud.org/about/board-meetings/")
    docs = []
    for page in range(1, cfg.get("max_pages", 5) + 1):
        url = base if page == 1 else urljoin(base, f"page/{page}/")
        try:
            soup, _ = _soup(url)
        except Exception as e:
            if page == 1:
                raise
            log.info("NTPUD page %d: %s", page, e)
            break
        page_dates = []
        for a in soup.find_all("a", href=re.compile(r"\.pdf$", re.I)):
            label = a.get_text(" ", strip=True).lower()
            fname = _filename(a["href"])
            d = parse_date(fname)
            if not d:
                continue
            page_dates.append(d)
            if "packet" in label or "packet" in fname.lower():
                if not ctx.packets:
                    continue
                kind = "Agenda packet"
            elif "minute" in label or "minute" in fname.lower():
                kind = "Minutes"
            else:
                kind = "Agenda"
            # "1-10122026-DP-Committee-Agenda1.pdf" / "DP-10122026-packet-print.pdf" -> "DP Committee" / "DP"
            words = re.sub(r"(?i)\.pdf$", "", fname).replace("_", "-").split("-")
            words = [w for w in words if not re.fullmatch(r"(?i)\d+|v\d+|(agenda|and|packet|print|minutes)\d*", w)]
            name = " ".join(words)
            docs.append(MeetingDoc(name or "Board Meeting", d, a["href"], kind))
        if not page_dates or min(page_dates) < ctx.meeting_window.start:
            break
    return scan_meeting_docs(cfg["name"], docs, ctx)


# ---------------------------------------------------------------- Tahoe Transportation
def ttd(cfg: dict, ctx: Context):
    """Tahoe Transportation District: WordPress 'meeting' posts; each page links its
    agenda packet PDF. Post dates aren't meeting dates, so read the date from the PDF
    file name (2026-10-7-TTD-...), then the URL slug, then the page text."""
    site = cfg.get("site", "https://tahoetransportation.org")
    posts = get(f"{site}/wp-json/wp/v2/meeting",
                params={"per_page": 40, "_fields": "link,title,date"}).json()
    # Posts are created shortly before the meeting; skip ones far older than the window.
    cutoff = ctx.meeting_window.start - timedelta(days=120)
    docs = []
    for p in posts:
        created = parse_date(p["date"][:10])
        if created and created < cutoff:
            continue
        title = BeautifulSoup(p["title"]["rendered"], "html.parser").get_text()
        try:
            soup, url = _soup(p["link"])
        except Exception as e:
            log.warning("TTD %s: %s", p["link"], e)
            continue
        main = soup.find("main") or soup
        pdfs = [urljoin(url, a["href"]) for a in main.find_all("a", href=re.compile(r"/wp-content/uploads/.+\.pdf$", re.I))]
        page_date = parse_date(p["link"], title, html_to_text(str(main))[:3000])
        title = re.sub(r"\s*[–-]\s*\w+ \d{1,2}, \d{4}\s*$", "", title)
        for pdf in pdfs:
            d = parse_date(_filename(pdf)) or page_date
            if d:
                kind = "Agenda packet" if "packet" in pdf.lower() else "Agenda"
                docs.append(MeetingDoc(title, d, pdf, kind))
    return scan_meeting_docs(cfg["name"], docs, ctx)


# ------------------------------------------------------------------- Lahontan Water Board
def lahontan(cfg: dict, ctx: Context):
    """Lahontan Regional Water Quality Control Board: one schedule page per year with a
    table of meeting dates and Agenda / Minutes links."""
    base = "https://www.waterboards.ca.gov/lahontan/board_info/agenda/"
    docs = []
    for year in range(ctx.meeting_window.start.year, ctx.meeting_window.end.year + 1):
        soup, url = _soup(f"{base}{year}_schedule.html")
        for row in soup.select("tr"):
            cells = row.find_all("td")
            if not cells:
                continue
            d = parse_date(f"{cells[0].get_text(' ', strip=True)} {year}")
            if not d:
                continue
            place = cells[1].get_text(" ", strip=True) if len(cells) > 1 else ""
            for a in row.find_all("a", href=True):
                label = a.get_text(" ", strip=True).lower()
                if "español" in label or "espanol" in label or not a["href"].lower().endswith(".pdf"):
                    continue
                kind = "Minutes" if "minute" in label else "Agenda"
                docs.append(MeetingDoc(f"Lahontan Water Board meeting ({place})".replace(" ()", ""),
                                       d, urljoin(url, a["href"]), kind))
    return scan_meeting_docs(cfg["name"], docs, ctx)


# ------------------------------------------------------------ California Tahoe Conservancy
def tahoe_conservancy(cfg: dict, ctx: Context):
    """California Tahoe Conservancy Board: a page per meeting (the agenda) that links to a
    'meeting documents' page of staff-report PDFs. The board meets quarterly, so staff
    reports are always scanned."""
    site = "https://tahoe.ca.gov"
    meetings = {}
    for listing in ("/board-meetings-agendas/", "/board-meetings-agendas/board-materials-archives/"):
        soup, url = _soup(site + listing)
        for a in soup.find_all("a", href=re.compile(r"conservancy-board-meeting-")):
            d = parse_date(a.get_text(" ", strip=True), a["href"])
            if d and ctx.meeting_window.contains(d):
                meetings[urljoin(url, a["href"])] = d

    docs = []
    for page, d in meetings.items():
        name = "Conservancy Board meeting"
        soup, url = _soup(page)
        main = soup.find("main") or soup
        docs.append(MeetingDoc(name, d, page, "Agenda"))
        materials = main.find("a", href=re.compile(r"meeting-documents"))
        if not materials:
            continue
        msoup, murl = _soup(urljoin(url, materials["href"]))
        mmain = msoup.find("main") or msoup
        for a in mmain.find_all("a", href=re.compile(r"\.pdf$", re.I)):
            label = a.get_text(" ", strip=True)
            if re.search(r"directions|anexo", label + a["href"], re.I):
                continue
            docs.append(MeetingDoc(name, d, urljoin(murl, a["href"]), f"Staff report: {label}"[:120]))
    return scan_meeting_docs(cfg["name"], docs, ctx)


def _kind(label: str) -> str:
    label = label.lower()
    if "minute" in label:
        return "Minutes"
    if "packet" in label or "board book" in label or "board-book" in label:
        return "Agenda packet"
    return "Agenda"


# -------------------------------------------------- South Tahoe PUD / Tahoe RCD (same CMS)
_MEETING_SLUG = re.compile(r"/(20\d\d-\d\d-\d\d)-[\w-]+/?$")


def streamline(cfg: dict, ctx: Context):
    """Sites whose meeting lists are a dated link per meeting ("/2026-10-15-board-meeting")
    followed by that meeting's PDFs ("/files/<id>/<name>.pdf"). Used by South Tahoe PUD
    and the Tahoe Resource Conservation District. Their agenda PDF is usually the full
    packet, so it is always scanned."""
    site = cfg["site"].rstrip("/")
    w = ctx.meeting_window
    docs = []
    for path in cfg.get("pages", ["/board-meetings"]):
        for year in range(w.start.year, w.end.year + 1):
            soup, url = _soup(f"{site}{path}?year={year}")
            main = soup.find("main") or soup
            current = None  # (date, name) of the meeting whose link we saw last
            for a in main.find_all("a", href=True):
                href = urljoin(url, a["href"])
                label = a.get_text(" ", strip=True)
                m = _MEETING_SLUG.search(href)
                if m and not label.lower().startswith("read more"):
                    name = re.sub(r"^[A-Z][a-z]{2} \d{1,2} 20\d\d\s+(Standing Committee\s+)?", "", label)
                    name = name or "Board meeting"
                    current = (parse_date(m[1]), name)
                elif "/files/" in href and href.lower().endswith(".pdf"):
                    fname = _filename(href)
                    d = current[0] if current else parse_date(fname)
                    if d:
                        name = current[1] if current else re.sub(r"\.pdf$", "", fname, flags=re.I)
                        docs.append(MeetingDoc(name, d, href, _kind(label + " " + fname)))
    return scan_meeting_docs(cfg["name"], docs, ctx)


# ---------------------------------------------------------- generic page of dated PDFs
def pdf_links(cfg: dict, ctx: Context):
    """Any page that lists meeting PDFs with the date in the link text or file name,
    e.g. Tahoe-Douglas Fire ("2026-09-23 BOT Agenda"). Config: pages, meeting_name,
    optional include (regex the link text/file name must match)."""
    include = re.compile(cfg.get("include", r"agenda|minutes|packet|board.?book"), re.I)
    docs = []
    for page in cfg["pages"]:
        soup, url = _soup(page)
        main = soup.find("main") or soup
        for a in main.find_all("a", href=re.compile(r"\.pdf($|\?)", re.I)):
            href = urljoin(url, a["href"])
            label = a.get_text(" ", strip=True)
            fname = _filename(href)
            if not include.search(label + " " + fname):
                continue
            d = parse_date(label, fname)
            if not d:
                continue
            name = cfg.get("meeting_name", "Board meeting")
            if "workshop" in (label + fname).lower():
                name += " (workshop)"
            docs.append(MeetingDoc(name, d, href, _kind(label + " " + fname)))
    return scan_meeting_docs(cfg["name"], docs, ctx)


# ------------------------------------------------------------------ North Tahoe Fire
def ntfire(cfg: dict, ctx: Context):
    """North Tahoe Fire Protection District: a blog post per meeting titled like
    "Regular Meeting 09-2026" linking Agenda/Minutes PDFs. Post dates are unreliable
    (posts are copied from old ones), so the day comes from the agenda's first page."""
    from ..fetch import document_pages
    from datetime import date as _date

    listing = cfg.get("url", "https://www.ntfire.net/board-minutes")
    soup, url = _soup(listing)
    w = ctx.meeting_window
    posts = {}
    for a in soup.find_all("a", href=re.compile(r"/board-minutes/(?!category|tag)")):
        title = a.get_text(" ", strip=True)
        m = re.search(r"(\d{1,2})-(20\d\d)", title)
        if not m or "meeting" not in title.lower():
            continue
        month_start = _date(int(m[2]), int(m[1]), 1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        if month_end >= w.start and month_start <= w.end:
            posts[urljoin(url, a["href"])] = (title, month_start)

    docs = []
    for post, (title, month_start) in posts.items():
        name = re.sub(r"\s*\d{1,2}-20\d\d\s*", " ", title).strip()
        psoup, purl = _soup(post)
        body = psoup.find("article") or psoup.find("main") or psoup
        pdfs = [(a.get_text(" ", strip=True), urljoin(purl, a["href"]))
                for a in body.find_all("a", href=re.compile(r"\.pdf($|\?)", re.I))]
        meeting_day = None
        for label, href in pdfs:
            if _kind(label) == "Agenda":
                try:
                    first = document_pages(href, ctx.use_cache)[0]
                    d = parse_date(first[:1500])
                    if d and d.year == month_start.year and d.month == month_start.month:
                        meeting_day = d
                except Exception as e:
                    log.info("NTFPD agenda %s: %s", href, e)
        for label, href in pdfs:
            docs.append(MeetingDoc(name, meeting_day or month_start, href, _kind(label)))
    return scan_meeting_docs(cfg["name"], docs, ctx)
