"""Municode Meetings (https://meetings.municode.com/MeetingsPage/index?clientCode=...)."""
from datetime import datetime
from urllib.parse import parse_qs, urlparse

from ..fetch import SESSION
from . import Context, MeetingDoc, scan_meeting_docs


def _direct(url: str) -> str:
    """Municode wraps files as /d/f?u=<blob url>&n=<name>; fetch the blob directly."""
    q = parse_qs(urlparse(url).query)
    return q["u"][0] if "u" in q else url


def run(cfg: dict, ctx: Context):
    r = SESSION.post("https://meetings.municode.com/api/publicMeetings/list", timeout=60, json={
        "displayClientCode": cfg["client_code"],
        "isDraft": False,
        "meetingTypeIds": [],
        "meetingDateFrom": f"{ctx.meeting_window.start:%Y-%m-%d}",
        "meetingDateTo": f"{ctx.meeting_window.end:%Y-%m-%d}",
    })
    r.raise_for_status()

    docs = []
    for m in r.json():
        name = m.get("meeting") or m.get("meetingType") or "Meeting"
        d = datetime.strptime(m["date"], "%m/%d/%Y").date()
        if m.get("agenda"):
            docs.append(MeetingDoc(name, d, _direct(m["agenda"]), "Agenda"))
        if m.get("minutes"):
            docs.append(MeetingDoc(name, d, _direct(m["minutes"]), "Minutes"))
        if ctx.packets and m.get("packet"):
            docs.append(MeetingDoc(name, d, _direct(m["packet"]), "Agenda packet"))

    return scan_meeting_docs(cfg["name"], docs, ctx)
