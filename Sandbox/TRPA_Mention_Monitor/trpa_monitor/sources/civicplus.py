"""CivicPlus AgendaCenter (https://<site>/AgendaCenter)."""
import logging
import re
from datetime import datetime

from bs4 import BeautifulSoup

from ..fetch import SESSION, get
from . import Context, MeetingDoc, scan_meeting_docs

log = logging.getLogger(__name__)
_ROW_DATE = re.compile(r"_(\d{2})(\d{2})(\d{4})-\d+")


def _rows(html: str, base: str, category: str | None, ctx: Context) -> list[MeetingDoc]:
    soup = BeautifulSoup(html, "html.parser")
    docs = []
    for row in soup.select("tr.catAgendaRow"):
        link = row.select_one('a[href*="/ViewFile/Agenda/_"]')
        if not link:
            continue
        m = _ROW_DATE.search(link["href"])
        d = datetime(int(m[3]), int(m[1]), int(m[2])).date()
        cat = category
        if cat is None:
            heading = row.find_parent("table").find_previous("h2")
            cat = heading.get_text(" ", strip=True) if heading else ""
        title = re.sub(r"\s*\(PDF\)\s*$", "", link.get_text(" ", strip=True))
        name = f"{cat}: {title}" if cat else title
        docs.append(MeetingDoc(name, d, base + link["href"], "Agenda"))
        minutes = row.select_one('a[href*="/ViewFile/Minutes/"]')
        if minutes:
            docs.append(MeetingDoc(name, d, base + minutes["href"], "Minutes"))
        packet = row.select_one('a[href*="packet=true"]')
        if ctx.packets and packet:
            docs.append(MeetingDoc(name, d, base + packet["href"], "Agenda packet"))
    return docs


def run(cfg: dict, ctx: Context):
    base = cfg["base_url"].rstrip("/")
    html = get(f"{base}/AgendaCenter", timeout=120).text
    docs = _rows(html, base, None, ctx)

    # The landing page only lists the current year; fetch other years the window reaches into.
    this_year = datetime.now().year
    w = ctx.meeting_window
    other_years = [y for y in range(w.start.year, w.end.year + 1) if y != this_year]
    if other_years:
        soup = BeautifulSoup(html, "html.parser")
        for table in soup.select('table[id^="table"]'):
            cat_id = table["id"][5:]
            heading = table.find_previous("h2")
            cat = heading.get_text(" ", strip=True) if heading else ""
            for year in other_years:
                try:
                    r = SESSION.post(f"{base}/AgendaCenter/UpdateCategoryList", timeout=60,
                                     data={"year": year, "catID": cat_id},
                                     headers={"X-Requested-With": "XMLHttpRequest"})
                    r.raise_for_status()
                    docs += _rows(r.text, base, cat, ctx)
                except Exception as e:
                    log.warning("%s: %s %s failed: %s", cfg["name"], cat, year, e)

    return scan_meeting_docs(cfg["name"], docs, ctx)
