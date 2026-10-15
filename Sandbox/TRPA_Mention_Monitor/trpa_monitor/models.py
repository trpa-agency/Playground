from dataclasses import dataclass, field
from datetime import date


@dataclass
class Mention:
    category: str            # "meeting" or "press"
    source: str              # e.g. "El Dorado County", "Google News"
    title: str               # meeting name or headline
    date: date | None
    url: str
    hit_count: int = 0
    snippets: list[str] = field(default_factory=list)
    detail: str = ""         # body name, outlet, document type, etc.
    verified: bool = True    # False = search-engine hit whose full text we couldn't check
    # Meetings only: how TRPA comes up, most significant first (see classify.py):
    # [{"type": "Agenda item", "title": "11. ...", "pages": [5], "count": 1, "in_title": True}, ...]
    contexts: list[dict] = field(default_factory=list)
    # Upcoming meetings only: matches for the department keywords in keywords.csv,
    # {"short-term rental": {"count": 4, "snippets": [...]}}
    keywords: dict[str, dict] = field(default_factory=dict)


@dataclass
class Window:
    start: date
    end: date

    def contains(self, d: date | None) -> bool:
        return d is not None and self.start <= d <= self.end
