"""Work out how TRPA comes up in a meeting document: as an agenda item, in public comment,
in a staff report, or in the minutes of an earlier meeting.

Agenda packets are a stack of documents: the agenda itself, then attachments (staff
reports, memos, minutes, correspondence, exhibits). The agenda is the opening pages, up to
the first page that starts an attachment. A mention on the agenda belongs to the agenda
item around it. A mention in an attachment takes that attachment's type, judged from the
page's running header, from an email or memo header earlier on the page, or from the
attachment it continues.
"""
import re
from collections import Counter

from .matcher import Matcher

AGENDA, PUBLIC, STAFF, MINUTES, OTHER = "Agenda item", "Public comment", "Staff report", "Minutes", "Attachment"
# Most significant first (orders contexts within a document); public comment matters least.
PRIORITY = [AGENDA, STAFF, OTHER, MINUTES, PUBLIC]

# Label for a document, from its most significant context. The app and PDF list upcoming
# meetings by date; only "public" changes the order (it is listed last).
#   "agenda"     TRPA (or a keyword) is part of an agendized item
#   "materials"  only in staff reports, attachments, or minutes
#   "public"     only in public comment or correspondence: flag as lower priority
IMPORTANCE = {AGENDA: "agenda", STAFF: "materials", OTHER: "materials", MINUTES: "materials", PUBLIC: "public"}
IMPORTANCE_LABEL = {"agenda": "On the agenda", "materials": "In meeting materials", "public": "Public comment only"}


def importance(contexts: list[dict]) -> str:
    """Importance level for a list of contexts ("" when there are none, e.g. press)."""
    types = {c["type"] for c in contexts}
    return IMPORTANCE[min(types, key=PRIORITY.index)] if types else ""


def sort_contexts(contexts: list[dict]) -> list[dict]:
    return sorted(contexts, key=lambda g: (PRIORITY.index(g["type"]), not g["in_title"], g["pages"][0]))

_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
_DATE = rf"(?:{_MONTH}\s+\d{{1,2}},?\s+\d{{4}}|\d{{1,2}}[ ./-]\d{{1,2}}[ ./-]\d{{2,4}})"

# Page-top markers (running headers and cover lines).
_AGENDA_HEAD = re.compile(r"\bAGENDA\b(?!\s*ITEM)|\bAgenda\s*[–-]|\bMeeting Agenda\b|\bAgenda Page\b")
# Real minutes carry the meeting date in their running header ("MEETING MINUTES: Sept. 17,
# 2026", "BOT Minutes 08 19 2026"); an agenda line like "City Council Meeting Minutes" doesn't.
_MINUTES_HEAD = re.compile(rf"\bminutes\b\W{{0,6}}{_DATE}|{_DATE}\W{{0,12}}(?:regular |special )?(?:board )?meeting minutes",
                           re.I)
_PUBLIC_HEAD = re.compile(
    r"provided .{0,80}by the public|public comments? (?:received|submitted)|written (?:public )?comments?"
    r"|comment letters?|correspondence received|public records? requ|make my comment part of the record", re.I)
# Report titles must start a line: agendas list attachments by name ("... Roll Change
# Request Staff Report"), which mustn't count.
_STAFF_HEAD = re.compile(
    r"M\s?E\s?M\s?O\s?R\s?A\s?N\s?D\s?U\s?M|^\s*(?:STAFF REPORT|Staff Report|BOARD REPORT)\b|Status Report\b"
    r"|^\s*TO:\s.*\n(?:.*\n){0,5}?\s*FROM:", re.M)
_NEW_DOC = re.compile(r"^\s*(?:Page 1 of \d+|1)\s*$|^\s*(?:ATTACHMENT|EXHIBIT)\s+[A-Z0-9]\b|RESOLUTION NO",
                      re.M)

# Mid-page starts.
_EMAIL = re.compile(r"^\s*From:\s.+\n(?:.*\n){0,4}?\s*(?:Sent|Date|To|Subject):", re.M)
_SUBJECT = re.compile(r"^\s*(?:SUBJECT|RE|Re|Subject):\s*(.+)$", re.M)
_LETTER = re.compile(r"^\s*Dear\s", re.M)

# Agenda item headings: "11.", "3. 26-1605 Chair ...", "A. For Possible Action: ...", "IV. ...", "A) ..."
_ITEM = re.compile(r"^\s*(?:Item\s+)?((?:\d{1,2}(?:\.\d{1,2})*[a-z]?|[A-Z]|[IVX]{1,5})[.)])(?:\s+(.*\S))?\s*$", re.M)
_PUBLIC_ITEM = re.compile(r"public (?:comment|forum|communication)|oral communication|comments? from the public", re.I)
_ORG_LINE = re.compile(r"^(?:[A-Z][\w.&'-]*\s+){0,6}(?:District|County|Agency|Authority|Commission|Council|Board|"
                       r"Inc\.?|City|Town)\s*$")


_PAGE_NO = re.compile(r"\s-\d+-\s|\bPage\s*[–-]?\s*\d+(?:\s+of\s+\d+)?\b|\s~\s*Page \d+\s*~", re.I)


def _clean(s: str, limit: int = 200) -> str:
    s = _PAGE_NO.sub(" ", s)   # running headers carry page numbers; drop them so pages group
    s = re.sub(r"\s+", " ", s).strip(" .;:–-")
    return s if len(s) <= limit else s[:limit].rsplit(" ", 1)[0] + "…"


def _meaningful_line(text: str, skip: set[str] = frozenset()) -> str:
    """First line that says what a document is: not a page number, running header, or org name."""
    for line in text.splitlines()[:25]:
        line = re.sub(r"\s+", " ", line).strip()
        if (len(line) < 4 or not re.search(r"[A-Za-z]{3}", line) or re.match(r"(?i)page \d+( of \d+)?$", line)
                or line in skip or _ORG_LINE.match(line)):
            continue
        if re.fullmatch(_DATE, line, re.I):
            return f"Letter dated {line}"
        return _clean(line, 140)
    return ""


def _page_kind(page: str) -> tuple[str | None, str]:
    """Type a page's opening text declares, or (None, "") if it doesn't say."""
    top = page.lstrip()[:600]
    head = top[:250]
    if _AGENDA_HEAD.search(head) and not _PUBLIC_HEAD.search(head[:120]):
        return "agenda", ""
    if re.search(r"public records? requ", head, re.I):
        return PUBLIC, "Public records request log"
    if _PUBLIC_HEAD.search(head) or _EMAIL.match(top):
        subject = _SUBJECT.search(page[:900])
        return PUBLIC, ("Email: " + _clean(subject.group(1), 120)) if (subject and _EMAIL.match(top)) else ""
    if _MINUTES_HEAD.search(head):
        return MINUTES, _clean(top.splitlines()[0] if top else "", 120)
    if _STAFF_HEAD.search(head):
        subject = _SUBJECT.search(page[:1500])
        return STAFF, _clean(subject.group(1), 140) if subject else ""
    return None, ""


def _running_headers(pages: list[str]) -> set[str]:
    """First lines that repeat across pages (running headers), to ignore in titles."""
    firsts = Counter(re.sub(r"\s+", " ", (p.strip().splitlines() or [""])[0]).strip() for p in pages)
    return {line for line, n in firsts.items() if n >= 2 and line}


def _agenda_item(pages: list[str], i: int, pos: int, skip: set[str]) -> tuple[str, bool]:
    """The agenda item around a mention: (label, mention is in the item's heading)."""
    page = pages[i]
    heads = list(_ITEM.finditer(page[:pos]))
    # Only trust a heading close above the mention: some agendas extract in column order,
    # so a distant heading may belong to a different item than the text below it.
    if heads and pos - heads[-1].start() < 400:
        h = heads[-1]
        start = h.start(2) if h.group(2) else h.end()
        stop = re.search(r"\n\s*\n|\n\s*(?:\d{1,2}[a-z]?|[A-Z]|[IVX]{1,5})[.)](?:\s|$)", page[start:])
        end = start + (stop.start() if stop else 300)
        return _clean(f"{h.group(1)} {page[start:end]}"), pos - start < 250
    # No heading close above (some agendas put the item number after the text): use the
    # paragraph around the mention.
    a = max(page.rfind("\n\n", 0, pos), page.rfind("\n \n", 0, pos))
    a = 0 if a < 0 else a
    b = page.find("\n\n", pos)
    para_lines = [ln for ln in page[a:b if b > 0 else len(page)].splitlines()
                  if re.sub(r"\s+", " ", ln).strip() not in skip]
    para = " ".join(para_lines)
    return _clean(para), (pos - a) < 300


def classify(pages: list[str], matcher: Matcher, doc_kind: str = "") -> list[dict]:
    """Group a document's counted TRPA mentions by how they come up.

    Returns [{"type", "title", "pages", "count", "in_title"}], most significant first.
    `doc_kind` is the collector's label for the file ("Agenda", "Minutes", "Staff report: ...").
    """
    if doc_kind.startswith("Staff report"):
        fixed = (STAFF, doc_kind.split(":", 1)[-1].strip())
    elif doc_kind == "Minutes":
        fixed = (MINUTES, "Minutes")
    else:
        fixed = None

    skip = _running_headers(pages)
    groups: dict[tuple[str, str], dict] = {}
    in_agenda = fixed is None
    current = fixed or (OTHER, "")

    for i, page in enumerate(pages):
        if not fixed:
            kind, title = _page_kind(page)
            if kind == "agenda":
                in_agenda = in_agenda or i == 0
            elif kind is not None:
                in_agenda = False
                # A continuation page (same type, no title of its own) keeps the title of
                # the attachment it continues.
                if not (kind == current[0] and not title and current[1]):
                    current = (kind, title or _meaningful_line(page, skip))
            elif not in_agenda and _NEW_DOC.search(page.lstrip()[:120]):
                current = (OTHER, _meaningful_line(page, skip))

        for h in matcher.hits(page):
            in_title = False
            if in_agenda:
                ctitle, in_title = _agenda_item(pages, i, h.start(), skip)
                ctype = PUBLIC if _PUBLIC_ITEM.search(ctitle[:60]) else AGENDA
            else:
                ctype, ctitle = current
                before = page[:h.start()]
                email = [m.start() for m in _EMAIL.finditer(before)]
                letter = [m.start() for m in _LETTER.finditer(before)]
                memo = [m.start() for m in _SUBJECT.finditer(before)]
                # "Dear" only starts a new piece when the page hasn't already said what it
                # is (a public records log can quote a letter); an email header always does.
                if ctype == PUBLIC and ctitle:
                    letter = []
                last_mail = max(email + letter, default=-1)
                if not fixed and last_mail > -1 and last_mail > max(memo, default=-1):
                    subj = _SUBJECT.search(page, last_mail)
                    label = ("Email: " if email and last_mail in email else "Letter: ") + (
                        _clean(subj.group(1), 110) if subj else "")
                    # A letter inside a staff report is part of that report, not public comment.
                    ctype, ctitle = (STAFF, f"{ctitle} (attached letter)") if ctype == STAFF else (PUBLIC, label.strip(": "))
                elif memo and ctype in (STAFF, OTHER) and not fixed:
                    ctype, ctitle = STAFF, _clean(page[memo[-1]:].split(":", 1)[1].splitlines()[0], 140)
            g = groups.setdefault((ctype, ctitle), {"type": ctype, "title": ctitle, "pages": [], "count": 0,
                                                     "in_title": False})
            g["count"] += 1
            g["in_title"] |= in_title
            if i + 1 not in g["pages"]:
                g["pages"].append(i + 1)
    return sort_contexts(list(groups.values()))


def primary(contexts: list[dict]) -> str:
    return contexts[0]["type"] if contexts else ""
