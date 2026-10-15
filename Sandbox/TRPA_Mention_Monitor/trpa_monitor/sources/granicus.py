"""Granicus ViewPublisher meeting archives (e.g. https://slt.granicus.com/ViewPublisher.php?view_id=6)."""
import re

from bs4 import BeautifulSoup

from ..dates import parse_date
from ..fetch import get
from . import Context, MeetingDoc, scan_meeting_docs


def run(cfg: dict, ctx: Context):
    host, view = cfg["host"], cfg.get("view_id", 1)
    html = get(f"https://{host}/ViewPublisher.php?view_id={view}", timeout=120).text
    soup = BeautifulSoup(html, "html.parser")

    docs = []
    # Granicus has several page templates; any table row holding an agenda/minutes link
    # is a meeting, with its name in the first cell and the date in another.
    for row in soup.find_all("tr"):
        if not row.find("a", href=re.compile(r"(Agenda|Minutes)Viewer")):
            continue
        cells = row.find_all("td")
        if not cells:
            continue
        name = re.sub(r"\s+", " ", cells[0].get_text(" ", strip=True)) or "Meeting"
        d = parse_date(*(c.get_text(" ") for c in cells[1:3]), name)
        if d is None:
            continue
        for a in row.find_all("a", href=True):
            href = a["href"]
            if href.startswith("//"):
                href = "https:" + href
            cell = a.find_parent("td")
            hdr = " ".join(cell.get_attribute_list("headers")) if cell and cell.get("headers") else ""
            if "AgendaViewer" in href:
                kind = "Agenda"
            elif "MinutesViewer" in href:
                kind = "Minutes"
            elif "Packet" in hdr and ctx.packets:
                kind = "Agenda packet"
            else:
                continue
            docs.append(MeetingDoc(name, d, href, kind))

    return scan_meeting_docs(cfg["name"], docs, ctx)
