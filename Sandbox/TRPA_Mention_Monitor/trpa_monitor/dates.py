"""Pull a meeting date out of free text, link text, URLs or file names."""
import re
from datetime import date, datetime

_MONTHS = ("january|february|march|april|may|june|july|august|september|october|november|december|"
           "jan|feb|mar|apr|jun|jul|aug|sept|sep|oct|nov|dec")
# "October 7, 2026", "Oct. 7 2026", "september-17-2026", "March 19 and 20, 2026"
_MONTH_DATE = re.compile(rf"\b({_MONTHS})\.?[\s_-]+(\d{{1,2}})(?:[\s_-]*(?:and|&|-)[\s_-]*\d{{1,2}})?,?[\s_-]+(\d{{4}})\b", re.I)
# "2026-10-07", "2026-9-16", "2026.10.15", "2026 08 19"
_ISO = re.compile(r"(?<![\d.])(20\d\d)[-_. ](\d{1,2})[-_. ](\d{1,2})(?![\d])")
# "10 13 2026", "10/13/2026", "10-13-2026"
_US = re.compile(r"\b(\d{1,2})[ ./_-](\d{1,2})[ ./_-](20\d\d)\b")
# "10132026" (NTPUD-style file names)
_PACKED = re.compile(r"(?<!\d)(\d{2})(\d{2})(20\d\d)(?!\d)")
# Last resort, two-digit year: "10.15.26", "09-23-26"
_US_SHORT = re.compile(r"(?<![\d.])(\d{1,2})[./_-](\d{1,2})[./_-](\d{2})(?![\d.])")


def _mk(y, m, d) -> date | None:
    try:
        return date(int(y), int(m), int(d))
    except ValueError:
        return None


def parse_date(*texts: str) -> date | None:
    """Return the first recognisable date found in the given strings (tried in order)."""
    for t in texts:
        if not t:
            continue
        t = re.sub(r"\s+", " ", t.replace("\xa0", " "))
        m = _MONTH_DATE.search(t)
        if m:
            month = m[1][:3].lower()
            try:
                d = datetime.strptime(f"{month} {m[2]} {m[3]}", "%b %d %Y").date()
                return d
            except ValueError:
                pass
        for rx, order in ((_ISO, (1, 2, 3)), (_US, (3, 1, 2)), (_PACKED, (3, 1, 2))):
            m = rx.search(t)
            if m and (d := _mk(*(m[i] for i in order))):
                return d
    for t in texts:
        m = _US_SHORT.search(t or "")
        if m and (d := _mk(2000 + int(m[3]), m[1], m[2])):
            return d
    return None
