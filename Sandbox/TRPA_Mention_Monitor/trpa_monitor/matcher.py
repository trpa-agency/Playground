import re


def _flex_spaces(pattern: str) -> str:
    """Let a literal space in a pattern match any run of whitespace, since PDF text often
    breaks lines mid-phrase ("Tahoe \nRegional"). Spaces inside [...] classes are left alone."""
    out, in_class, escaped = [], False, False
    for ch in pattern:
        if escaped:
            out.append(ch); escaped = False
        elif ch == "\\":
            out.append(ch); escaped = True
        elif ch == "[":
            in_class = True; out.append(ch)
        elif ch == "]":
            in_class = False; out.append(ch)
        elif ch == " " and not in_class:
            out.append(r"\s+")
        else:
            out.append(ch)
    return "".join(out)


def keyword_pattern(phrase: str) -> str:
    """A plain word or phrase as a whole-word pattern that tolerates line breaks and a
    simple plural ("short-term rental" also matches "short-term rentals")."""
    words = [re.escape(w) for w in phrase.split()]
    return r"(?<!\w)" + r"[\s\-]+".join(words) + r"(?:s|es)?(?!\w)"


def load_departments(path) -> dict[str, list[str]]:
    """Keywords by department from keywords.csv ("department,keyword" columns, one row per
    keyword; a keyword may be listed under several departments). A plain .txt file (one
    phrase per line, # comments) is read as a single "General" department."""
    from pathlib import Path
    import csv
    path = Path(path)
    if not path.exists():
        return {}
    out: dict[str, list[str]] = {}
    if path.suffix.lower() == ".txt":
        rows = [("General", line.split("#", 1)[0]) for line in path.read_text(encoding="utf-8").splitlines()]
    else:
        with path.open(encoding="utf-8-sig", newline="") as f:
            rows = [((r.get("department") or "").strip() or "General", r.get("keyword") or "")
                    for r in csv.DictReader(f)]
    for dept, kw in rows:
        kw = " ".join(kw.split())
        if kw and kw.lower() not in {k.lower() for k in out.get(dept, [])}:
            out.setdefault(dept, []).append(kw)
    return out


def flatten_keywords(departments: dict[str, list[str]]) -> list[str]:
    """Every department's keywords, once each (first spelling wins)."""
    seen, out = set(), []
    for kws in departments.values():
        for kw in kws:
            if kw.lower() not in seen:
                seen.add(kw.lower())
                out.append(kw)
    return out


class Matcher:
    def __init__(self, patterns: list[str], ignore: list[str] = (), context: int = 160):
        self.regex = re.compile("|".join(f"(?:{p})" for p in patterns), re.IGNORECASE)
        # Boilerplate phrases (e.g. a standing list of board liaison assignments) whose
        # TRPA mention shouldn't count. Matched against text around each hit.
        self.ignore = [re.compile(_flex_spaces(p), re.IGNORECASE) for p in ignore]
        self.context = context

    def _ignored(self, text: str, m: re.Match) -> bool:
        """True if the hit sits inside a boilerplate phrase (the phrase must contain the hit)."""
        a = max(0, m.start() - 300)
        around = text[a:m.end() + 300]
        start, end = m.start() - a, m.end() - a
        return any(b.start() <= start and end <= b.end()
                   for p in self.ignore for b in p.finditer(around))

    def hits(self, text: str) -> list[re.Match]:
        """Every counted mention (boilerplate excluded)."""
        return [m for m in self.regex.finditer(text or "") if not self._ignored(text, m)]

    def find(self, text: str, max_snippets: int = 5) -> tuple[int, list[str]]:
        """Return (number of hits, a few context snippets)."""
        if not text:
            return 0, []
        hits = self.hits(text)
        snippets: list[str] = []
        last_end = -1
        for m in hits:
            if len(snippets) >= max_snippets:
                break
            if m.start() < last_end:  # already inside the previous snippet
                continue
            a = max(0, m.start() - self.context)
            b = min(len(text), m.end() + self.context)
            snippet = re.sub(r"\s+", " ", text[a:b]).strip()
            snippets.append(("..." if a else "") + snippet + ("..." if b < len(text) else ""))
            last_end = b
        return len(hits), snippets
