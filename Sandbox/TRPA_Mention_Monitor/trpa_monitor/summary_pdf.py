"""Printable summary of TRPA mentions (data/TRPA_Mention_Summary.pdf).

Leads with upcoming meetings whose posted agendas mention TRPA, then summarizes past
meeting mentions and press coverage. Follows the trpa-brand skill for agency documents:
Calibri 11 pt (Carlito or Helvetica if Calibri isn't installed), TRPA navy text, TRPA blue
headings, and TRPA style-guide writing (Oct. 15, 2026; one to nine spelled out; Oxford comma).
"""
import logging
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from .classify import importance
from .models import Mention, Window

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent

# ── Brand ──
NAVY = colors.HexColor("#003B71")
BLUE = colors.HexColor("#0072CE")
ORANGE = colors.HexColor("#E87722")
ORANGE_TEXT = colors.HexColor("#B55A10")     # text-sized orange (AA on white)
ORANGE_LIGHT = colors.HexColor("#FDF3EA")
GRAY_TEXT = colors.HexColor("#6B7688")
GRAY_BORDER = colors.HexColor("#E2E6EC")
GRAY_BG = colors.HexColor("#F5F7FA")
BLUE_LIGHT = colors.HexColor("#E8F1F8")
MARK_BG = "#FDF3EA"

TRPA_RE = re.compile(r"Tahoe\s+Regional\s+Planning\s+Agency|\bTRPA\b", re.I)
_HIGHLIGHT = TRPA_RE   # TRPA plus any keywords; set by write_summary_pdf


def _set_terms(keywords) -> None:
    global _HIGHLIGHT
    from .matcher import keyword_pattern
    _HIGHLIGHT = re.compile("|".join([TRPA_RE.pattern] + [keyword_pattern(k) for k in keywords]), re.I)
MONTHS = ["Jan.", "Feb.", "March", "April", "May", "June", "July", "Aug.", "Sept.", "Oct.", "Nov.", "Dec."]
NUMBER_WORDS = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]


def _register_fonts() -> tuple[str, str, str]:
    """Calibri per the TRPA style guide; Carlito (metric-compatible) or Helvetica elsewhere."""
    candidates = [
        ("Calibri", Path("C:/Windows/Fonts"), "calibri.ttf", "calibrib.ttf", "calibrii.ttf"),
        ("Carlito", Path("/usr/share/fonts/truetype/crosextra"), "Carlito-Regular.ttf", "Carlito-Bold.ttf", "Carlito-Italic.ttf"),
    ]
    for name, folder, reg, bold, ital in candidates:
        if all((folder / f).exists() for f in (reg, bold, ital)):
            pdfmetrics.registerFont(TTFont(name, str(folder / reg)))
            pdfmetrics.registerFont(TTFont(name + "-Bold", str(folder / bold)))
            pdfmetrics.registerFont(TTFont(name + "-Italic", str(folder / ital)))
            pdfmetrics.registerFontFamily(name, normal=name, bold=name + "-Bold", italic=name + "-Italic",
                                          boldItalic=name + "-Bold")
            return name, name + "-Bold", name + "-Italic"
    return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"


FONT, FONT_BOLD, FONT_ITALIC = _register_fonts()


# ── Formatting (TRPA style guide) ──
def fmt_date(d: date | None, year: bool = True) -> str:
    if not d:
        return "—"
    return f"{MONTHS[d.month - 1]} {d.day}" + (f", {d.year}" if year else "")


def weekday(d: date) -> str:
    return d.strftime("%A")


def count(n: int, noun: str, plural: str | None = None) -> str:
    word = NUMBER_WORDS[n] if n < 10 else f"{n:,}"
    return f"{word} {noun if n == 1 else (plural or noun + 's')}"


def num(n: int) -> str:
    return NUMBER_WORDS[n] if 0 < n < 10 else f"{n:,}"


def cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def series(items: list[str]) -> str:
    """Oxford-comma list."""
    if len(items) <= 2:
        return " and ".join(items)
    return ", ".join(items[:-1]) + ", and " + items[-1]


def countdown(d: date, today: date) -> str:
    n = (d - today).days
    if n <= 0:
        return "Today"
    if n == 1:
        return "Tomorrow"
    return f"In {count(n, 'day')}"


# ── Passages and links ──
def split_page(snippet: str) -> tuple[int | None, str]:
    m = re.match(r"p\.(\d+):\s*", snippet or "")
    return (int(m[1]), snippet[m.end():]) if m else (None, snippet or "")


def key_passage(snippet: str, limit: int = 320) -> tuple[int | None, str]:
    """Trim a snippet to the sentence(s) around its first TRPA mention."""
    page, text = split_page(snippet)
    # Snippets arrive with "..." where the collector cut them; work on the bare text.
    text = re.sub(r"\s+", " ", text).strip()
    cut_left, cut_right = text.startswith("..."), text.endswith("...")
    text = text.strip(".").strip() if (cut_left or cut_right) else text
    m = _HIGHLIGHT.search(text)
    if not m:
        return page, text[:limit]
    # Sentence starts, plus datelines ("LAKE TAHOE, Nev. – The agency ...") and bullets.
    starts = [s.end() for s in re.finditer(r"(?:[.!?]|\s[–—]|•)\s+(?=[A-Z0-9“\"(])", text[:m.start()])]
    a = starts[-1] if starts else 0
    e = re.search(r"[.!?](\s|$)", text[m.end():])
    b = m.end() + e.end() if e else len(text)
    if b - a < 60:                          # too short to be useful; keep the whole snippet
        a, b = 0, len(text)
    out = text[a:b].strip()
    if len(out) > limit:
        out, b = out[:limit].rsplit(" ", 1)[0], -1
    if a > 0 or cut_left:
        out = "…" + out
    if (b == -1 or b < len(text) or cut_right) and not out.endswith((".", "!", "?")):
        out += "…"
    return page, out


def marked(text: str) -> str:
    """Escape for Paragraph markup and highlight TRPA mentions."""
    return _HIGHLIGHT.sub(lambda m: f'<font name="{FONT_BOLD}"><span backColor="{MARK_BG}">{m.group(0)}</span></font>',
                       escape(text))


def first_page(m: Mention) -> int | None:
    """Page of the first TRPA mention, or of the first keyword match if TRPA isn't mentioned."""
    snippets = m.snippets or [s for k in m.keywords.values() for s in k["snippets"]]
    return split_page(snippets[0])[0] if snippets else None


def page_list(pages: list[int]) -> str:
    if len(pages) == 1:
        return f"page {pages[0]}"
    if pages == list(range(pages[0], pages[-1] + 1)):
        return f"pages {pages[0]}–{pages[-1]}"
    shown = [str(p) for p in pages[:4]]
    return "pages " + (series(shown) if len(pages) <= 4 else ", ".join(shown) + ", and others")


def download_only(url: str) -> bool:
    return "GetMeetingFileStream" in (url or "")


def doc_url(m: Mention, page: int | None = None) -> str:
    page = page or first_page(m)
    if m.category == "press" or not page or download_only(m.url):
        return m.url
    return m.url.split("#")[0] + f"#page={page}"


def link(url: str, label: str) -> str:
    return f'<link href="{escape(url, {chr(34): "&quot;"})}" color="#0072CE"><u>{escape(label)}</u></link>'


def open_label(m: Mention, noun: str = "agenda") -> str:
    page = first_page(m)
    if m.category == "press":
        return "Open article"
    if not page:
        return f"Open {noun}"
    return f"Download {noun} (see page {page})" if download_only(m.url) else f"Open {noun} at page {page}"


# ── Styles ──
def _styles() -> dict[str, ParagraphStyle]:
    base = ParagraphStyle("body", fontName=FONT, fontSize=11, leading=13.5, textColor=NAVY, alignment=TA_LEFT)
    return {
        "body": base,
        "h2": ParagraphStyle("h2", parent=base, fontName=FONT_BOLD, fontSize=15, leading=19, spaceBefore=14, spaceAfter=4),
        "intro": ParagraphStyle("intro", parent=base, textColor=GRAY_TEXT, fontSize=10.5, spaceAfter=8),
        "when": ParagraphStyle("when", parent=base, fontName=FONT_BOLD, fontSize=12, leading=15),
        "agency": ParagraphStyle("agency", parent=base, fontName=FONT_BOLD, fontSize=12.5, leading=16),
        "meta": ParagraphStyle("meta", parent=base, fontSize=10, leading=12.5, textColor=GRAY_TEXT, spaceAfter=3),
        "passage": ParagraphStyle("passage", parent=base, fontSize=10.5, leading=13, leftIndent=8, spaceBefore=3),
        "how": ParagraphStyle("how", parent=base, fontSize=10, leading=12.5, spaceBefore=1),
        "flag": ParagraphStyle("flag", parent=base, fontSize=11, leading=15, spaceAfter=4),
        "h3": ParagraphStyle("h3", parent=base, fontName=FONT_BOLD, fontSize=12.5, leading=16, spaceBefore=8,
                             spaceAfter=3),
        "cell": ParagraphStyle("cell", parent=base, fontSize=9.5, leading=11.5),
        "cell_meta": ParagraphStyle("cell_meta", parent=base, fontSize=8.5, leading=10.5, textColor=GRAY_TEXT),
        "cell_head": ParagraphStyle("cell_head", parent=base, fontName=FONT_BOLD, fontSize=9.5, leading=11.5),
        "note": ParagraphStyle("note", parent=base, fontSize=9.5, leading=12, textColor=GRAY_TEXT),
        "bullet": ParagraphStyle("bullet", parent=base, fontSize=10, leading=12.5, leftIndent=12, bulletIndent=2, spaceAfter=2),
    }


# ── Page decoration ──
class _NumberedCanvas(rl_canvas.Canvas):
    """Adds "Page X of Y" once the total page count is known."""
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._pages = []

    def showPage(self):
        self._pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._pages)
        for state in self._pages:
            self.__dict__.update(state)
            self.setFont(FONT, 8.5)
            self.setFillColor(GRAY_TEXT)
            self.drawRightString(letter[0] - 0.75 * inch, 0.5 * inch, f"Page {self._pageNumber} of {total}")
            super().showPage()
        super().save()


def _decorate(title_date: str, window: Window):
    logo = ROOT / "assets" / "trpa-logo-white.png"

    def first(c: rl_canvas.Canvas, doc):
        w, h = letter
        band = 1.15 * inch
        c.saveState()
        c.setFillColor(NAVY)
        c.rect(0, h - band, w, band, stroke=0, fill=1)
        x = 0.75 * inch
        if logo.exists():
            c.drawImage(str(logo), x, h - band + 0.22 * inch, height=0.71 * inch, width=0.71 * inch * 428 / 255,
                        mask="auto")
            x += 0.71 * inch * 428 / 255 + 0.22 * inch
            c.setStrokeColor(colors.Color(1, 1, 1, alpha=0.4))
            c.line(x - 0.11 * inch, h - band + 0.22 * inch, x - 0.11 * inch, h - 0.22 * inch)
        c.setFillColor(colors.white)
        c.setFont(FONT_BOLD, 20)
        c.drawString(x, h - 0.55 * inch, "TRPA Mention Summary")
        c.setFont(FONT, 10.5)
        c.drawString(x, h - 0.80 * inch,
                     f"Lake Tahoe Region public meetings and press · Prepared {title_date}")
        _footer(c)
        c.restoreState()

    def later(c: rl_canvas.Canvas, doc):
        c.saveState()
        c.setFont(FONT, 8.5)
        c.setFillColor(GRAY_TEXT)
        c.drawString(0.75 * inch, letter[1] - 0.5 * inch, f"TRPA Mention Summary · {title_date}")
        c.setStrokeColor(GRAY_BORDER)
        c.line(0.75 * inch, letter[1] - 0.56 * inch, letter[0] - 0.75 * inch, letter[1] - 0.56 * inch)
        _footer(c)
        c.restoreState()

    def _footer(c):
        c.setFont(FONT, 8.5)
        c.setFillColor(GRAY_TEXT)
        c.drawString(0.75 * inch, 0.5 * inch, "Compiled by the Tahoe Regional Planning Agency from agency agendas and news sources.")

    return first, later


# ── Sections ──
def _upcoming_block(st, m: Mention, today: date, width: float) -> KeepTogether:
    # Passages: up to three for TRPA, then up to two per keyword.
    seen, passages = set(), []
    groups = [(m.snippets, 3)] + [(k["snippets"], 2) for k in m.keywords.values()]
    for snippets, cap in groups:
        taken = 0
        for s in snippets:
            page, text = key_passage(s)
            if text in seen or taken == cap:
                continue
            seen.add(text)
            passages.append((page, text))
            taken += 1
    passages = passages[:5]

    trpa = count(m.hit_count, "TRPA mention") if m.hit_count else "no TRPA mentions"
    # Meetings that name TRPA stand out from keyword-only matches: a label and a blue panel.
    names_trpa = m.hit_count > 0
    flag = [Paragraph(f'<font name="{FONT_BOLD}" color="#FFFFFF" backColor="#003B71">&nbsp;MENTIONS TRPA&nbsp;</font>',
                      st["flag"])] if names_trpa else []
    body = flag + [
        Paragraph(f'{weekday(m.date)}, {fmt_date(m.date)} '
                  f'<font color="#B55A10" size="10">{countdown(m.date, today)}</font>', st["when"]),
        Paragraph(escape(m.source), st["agency"]),
        Paragraph(f"{escape(m.title)} · {escape(m.detail)} · {trpa}", st["meta"]),
    ]
    if m.keywords:
        terms = series([f"“{escape(k)}” ({num(v['count'])})" for k, v in m.keywords.items()])
        body.append(Paragraph(f'<font name="{FONT_BOLD}">Keywords:</font> {terms}', st["meta"]))
    # How the terms come up: agenda item, public comment, staff report, minutes.
    for c in m.contexts[:4]:
        where = page_list(c["pages"])
        title = f": {marked(c['title'])}" if c["title"] else ""
        # Only claim "named in the item" when the term is visibly in the item's title.
        named = (" · named in the item itself" if c["type"] == "Agenda item" and c["in_title"]
                 and _HIGHLIGHT.search(c["title"][:140]) else "")
        body.append(Paragraph(f'<font name="{FONT_BOLD}" color="#003B71">{escape(c["type"])}</font>{title} '
                              f'<font color="#6B7688">({where}{named})</font>', st["how"]))
    if len(m.contexts) > 4:
        body.append(Paragraph(f'<font color="#6B7688">…and {num(len(m.contexts) - 4)} more places in the '
                              f'document</font>', st["how"]))
    for page, text in passages:
        prefix = f'<font name="{FONT_BOLD}">Page {page}:</font> ' if page else ""
        body.append(Paragraph(prefix + marked(text), st["passage"]))
    more = m.hit_count - sum(len(TRPA_RE.findall(t)) for _, t in passages)
    tail = link(doc_url(m), open_label(m))
    if more > 0:
        tail += (f'  <font color="#6B7688">· {num(more)} more TRPA '
                 f'{"mention" if more == 1 else "mentions"} in the document</font>')
    body.append(Spacer(1, 3))
    body.append(Paragraph(tail, st["meta"]))
    t = Table([[body]], colWidths=[width])
    t.setStyle(TableStyle([
        ("LINEBEFORE", (0, 0), (0, -1), 5 if names_trpa else 3, NAVY if names_trpa else ORANGE),
        ("BOX", (0, 0), (-1, -1), 0.75 if names_trpa else 0.5, NAVY if names_trpa else GRAY_BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), BLUE_LIGHT if names_trpa else colors.white),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return KeepTogether([t, Spacer(1, 8)])


def _table(st, header: list[str], rows: list[list], widths: list[float]) -> Table:
    data = [[Paragraph(h, st["cell_head"]) for h in header]] + rows
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GRAY_BG),
        ("LINEBELOW", (0, 0), (-1, 0), 0.75, GRAY_BORDER),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, GRAY_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _press_passage(m: Mention) -> str:
    """First passage that isn't just the headline (an article's first mention is often
    its own title, followed by site navigation text)."""
    head = re.sub(r"\W+", " ", m.title).lower().strip()[:40]
    passages = [key_passage(s)[1] for s in m.snippets]
    for p in passages:
        if head and head not in re.sub(r"\W+", " ", p).lower():
            return p
    return passages[0] if passages else ""


def _top(counter: Counter, unit: str, n: int = 4) -> str:
    items = counter.most_common(n)
    return series([f"{escape(name)} ({count(c, unit)})" for name, c in items])


def write_summary_pdf(path: Path, mentions: list[Mention], window: Window, meeting_window: Window,
                      sources: list[dict], generated: datetime | None = None, keywords: list[str] = (),
                      departments: dict[str, list[str]] | None = None):
    generated = generated or datetime.now()
    _set_terms(keywords)
    today = window.end
    st = _styles()
    width = letter[0] - 1.5 * inch

    upcoming = sorted((m for m in mentions if m.category == "upcoming"), key=lambda m: (m.date, m.source))
    past = sorted((m for m in mentions if m.category == "meeting"), key=lambda m: m.date, reverse=True)
    press = sorted((m for m in mentions if m.category == "press"), key=lambda m: m.date or date.min, reverse=True)
    agenda_items = [m for m in upcoming if importance(m.contexts) == "agenda"]
    # Upcoming meetings are listed by date whether TRPA is an agenda item or in the packet;
    # only public-comment-only mentions are set apart as lower priority.
    public_only = [m for m in upcoming if importance(m.contexts) == "public"]
    main_upcoming = [m for m in upcoming if importance(m.contexts) != "public"]
    n_trpa = sum(1 for m in main_upcoming if m.hit_count)

    story = [Spacer(1, 0.55 * inch)]

    # At a glance
    story.append(Paragraph("At a glance", st["h2"]))
    what = "TRPA or a keyword" if keywords else "TRPA"
    # Name the departments rather than every keyword; keywords.csv has the full list.
    dept_names = series([escape(d) for d in departments]) if departments else ""
    terms = (f" or one of the department keywords in keywords.csv ({dept_names})" if dept_names
             else f" or one of these keywords: {series(['“' + escape(k) + '”' for k in keywords])}" if keywords
             else "")
    if main_upcoming:
        nxt = main_upcoming[0]
        lead = (f"{cap(count(len(main_upcoming), 'upcoming meeting document'))} "
                f"{'mentions' if len(main_upcoming) == 1 else 'mention'} {what}"
                + (f"; {num(n_trpa)} of {'it' if len(main_upcoming) == 1 else 'them'} "
                   f"{'names' if n_trpa == 1 else 'name'} TRPA" if keywords else "")
                + (f", and {num(len(agenda_items))} {'includes' if len(agenda_items) == 1 else 'include'} a match "
                   f"as an agenda item" if agenda_items else "")
                + f". The next is {weekday(nxt.date)}, {fmt_date(nxt.date, False)}: {escape(nxt.source)}, "
                f"{escape(nxt.title)}.")
    else:
        lead = f"None of the agendas posted so far mention {what} outside public comment."
    if public_only:
        lead += (f" {what} comes up only in public comment in "
                 f"{count(len(public_only), 'more', 'more')}, which {'is' if len(public_only) == 1 else 'are'} "
                 f"lower priority.")
    outlets = {m.detail or m.source for m in press}
    lead += (f" Over the past 30 days ({fmt_date(window.start)} to {fmt_date(window.end)}), TRPA came up in "
             f"{count(len(past), 'meeting document')} from {count(len({m.source for m in past}), 'agency', 'agencies')} "
             f"and in {count(len(press), 'press item')} from {count(len(outlets), 'outlet')}.")
    story.append(Paragraph(lead, st["body"]))

    # Upcoming meetings
    story.append(Paragraph("Upcoming meetings", st["h2"]))
    story.append(Paragraph(
        f"Meetings that haven't happened yet whose posted agenda or packet mentions TRPA"
        + terms
        + f". Meetings that mention TRPA or Tahoe Regional Planning Agency come first, highlighted in blue "
        f"and labelled “Mentions TRPA”; meetings that match a department keyword only follow. Each group is "
        f"soonest first. "
        f"Mentions only in public comment are listed last as lower priority. "
        f"Agendas checked through {fmt_date(meeting_window.end)}; most agencies post three to 10 days ahead.",
        st["intro"]))
    # TRPA mentions first, then keyword-only matches (each already soonest first).
    trpa_up = [m for m in main_upcoming if m.hit_count]
    keyword_up = [m for m in main_upcoming if not m.hit_count]
    if keyword_up or trpa_up:
        story.append(Paragraph("Mentions TRPA", st["h3"]))
        story += ([_upcoming_block(st, m, today, width) for m in trpa_up] if trpa_up else
                  [Paragraph("None of the agendas posted so far mention TRPA by name.", st["intro"])])
    if keyword_up:
        blocks = [_upcoming_block(st, m, today, width) for m in keyword_up]
        # Keep the heading on the same page as its first meeting.
        story.append(KeepTogether([Paragraph("Department keyword matches", st["h3"]), blocks[0]]))
        story += blocks[1:]
    if public_only:
        story.append(Paragraph('Public comment only <font size="10" color="#6B7688">(lower priority)</font>',
                               st["h3"]))
        rows = []
        for m in public_only:
            first = (m.snippets or [s for k in m.keywords.values() for s in k["snippets"]] or [""])[0]
            _, text = key_passage(first)
            c = m.contexts[0] if m.contexts else {}
            rows.append([
                Paragraph(f'{fmt_date(m.date)}<br/>{countdown(m.date, today)}', st["cell_meta"]),
                Paragraph(f'<font name="{FONT_BOLD}">{escape(m.source)}</font><br/>{escape(m.title)}'
                          f'<br/>{escape(c.get("title", ""))[:90]}', st["cell_meta"]),
                Paragraph(marked(text[:240]) + "<br/>" + link(doc_url(m), open_label(m)), st["cell_meta"]),
            ])
        story.append(_table(st, ["Date", "Agency and meeting", "Passage"], rows,
                            [0.85 * inch, 2.2 * inch, width - 3.05 * inch]))
    if not upcoming:
        story.append(Paragraph("No upcoming meetings yet. Check the next update.", st["body"]))

    # Past meetings
    story.append(Paragraph("Past meetings", st["h2"]))
    if past:
        by_agency = Counter(m.source for m in past)
        story.append(Paragraph(
            f"{count(len(past), 'meeting document').capitalize()} from "
            f"{count(len(by_agency), 'agency', 'agencies')} mentioned TRPA between {fmt_date(window.start)} and "
            f"{fmt_date(window.end)}. Most often: {_top(by_agency, 'document')}.", st["intro"]))
        rows = []
        for m in past:
            page, text = key_passage(m.snippets[0]) if m.snippets else (None, "")
            level = importance(m.contexts)
            how = f" · {escape(m.contexts[0]['type'])}" if m.contexts else ""
            if level == "public":
                how = " · public comment only"
            rows.append([
                Paragraph(fmt_date(m.date), st["cell"]),
                Paragraph(f'<font name="{FONT_BOLD}">{escape(m.source)}</font><br/>{escape(m.title)}'
                          f'<br/><font color="#6B7688">{escape(m.detail)}{how}</font>', st["cell"]),
                Paragraph(str(m.hit_count), st["cell"]),
                Paragraph((f'<font name="{FONT_BOLD}">p. {page}:</font> ' if page else "") + marked(text)
                          + "<br/>" + link(doc_url(m), open_label(m, "document")), st["cell"]),
            ])
        story.append(_table(st, ["Date", "Agency and meeting", "Mentions", "Key passage"], rows,
                            [0.85 * inch, 1.9 * inch, 0.8 * inch, width - 3.55 * inch]))
        story.append(Paragraph("Source: agendas, minutes, and agenda packets published by each agency.", st["note"]))
    else:
        story.append(Paragraph("No past meeting documents mentioned TRPA in this period.", st["body"]))

    # Press
    story.append(Paragraph("Press coverage", st["h2"]))
    if press:
        by_outlet = Counter(m.detail or m.source for m in press)
        unverified = sum(1 for m in press if not m.verified)
        note = (f" {count(unverified, 'item').capitalize()} {'is a' if unverified == 1 else 'are'} headline "
                f"{'match' if unverified == 1 else 'matches'} only; the article text couldn't be checked."
                if unverified else "")
        story.append(Paragraph(
            f"{count(len(press), 'press item').capitalize()} from {count(len(by_outlet), 'outlet')} mentioned TRPA. "
            f"Most coverage: {_top(by_outlet, 'item')}.{note}", st["intro"]))
        rows = []
        for m in press:
            text = _press_passage(m)
            check = "" if m.verified else '<br/><font color="#6B7688"><i>Headline match only</i></font>'
            rows.append([
                Paragraph(fmt_date(m.date), st["cell"]),
                Paragraph(link(m.url, m.title) + f'<br/><font color="#6B7688">{escape(m.detail or m.source)}</font>'
                          + check, st["cell"]),
                Paragraph(marked(text), st["cell"]),
            ])
        story.append(_table(st, ["Date", "Headline and outlet", "Key passage"], rows,
                            [0.85 * inch, 2.6 * inch, width - 3.45 * inch]))
        story.append(Paragraph("Source: Google News, Bing News, and local news RSS feeds.", st["note"]))
    else:
        story.append(Paragraph("No press items mentioned TRPA in this period.", st["body"]))

    # About
    story.append(Paragraph("About this summary", st["h2"]))
    n_meet = sum(1 for s in sources if s["kind"] == "meetings")
    n_press = sum(1 for s in sources if s["kind"] == "press")
    problems = [s for s in sources if not s["ok"] or s.get("docs_unreadable")]
    bullets = [
        f"Checked {count(n_meet, 'local agency', 'local agencies')} and {count(n_press, 'news source')} "
        f"on {fmt_date(generated.date())}. Full text of agendas, minutes, and packets was searched for "
        f"“Tahoe Regional Planning Agency” and “TRPA.”",
        "TRPA Governing Board and Advisory Planning Commission (APC) meetings are excluded, as is trpa.gov.",
        "Recurring boilerplate is ignored, such as meeting locations at TRPA's offices and “Sources: TRPA” map credits.",
    ]
    if dept_names:
        bullets.append(f"Upcoming meetings were also searched for {count(len(keywords), 'department keyword')} "
                       f"from keywords.csv, grouped by department: {dept_names}.")
    elif keywords:
        bullets.append("Upcoming meetings were also searched for these keywords: "
                       + series([f"“{escape(k)}”" for k in keywords]) + ".")
    bullets.append("“How it comes up” is worked out from each document's structure (agenda pages, memo and "
                   "email headers, minutes headers), so treat it as a guide and confirm in the document.")
    if problems:
        bullets.append("Not fully checked: " + series([escape(s["name"]) for s in problems]) + ".")
    story += [Paragraph(b, st["bullet"], bulletText="•") for b in bullets]

    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(path), pagesize=letter, leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                            topMargin=0.8 * inch, bottomMargin=0.8 * inch,
                            title="TRPA Mention Summary", author="Tahoe Regional Planning Agency",
                            subject=f"TRPA mentions, {fmt_date(window.start)} to {fmt_date(window.end)}")
    first, later = _decorate(fmt_date(generated.date()), window)
    doc.build(story, onFirstPage=first, onLaterPages=later, canvasmaker=_NumberedCanvas)
