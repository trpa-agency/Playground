"""CivicClerk public portal (https://<tenant>.portal.civicclerk.com), via its OData API."""
from datetime import datetime, timedelta

from ..fetch import get
from . import Context, MeetingDoc, scan_meeting_docs

KINDS = {"Agenda": "Agenda", "Minutes": "Minutes", "Agenda Packet": "Agenda packet"}


def run(cfg: dict, ctx: Context):
    api = f"https://{cfg['tenant']}.api.civicclerk.com/v1"
    w = ctx.meeting_window
    events = get(f"{api}/Events", params={
        "$filter": f"startDateTime ge {w.start:%Y-%m-%d}T00:00:00Z and "
                   f"startDateTime lt {w.end + timedelta(days=1):%Y-%m-%d}T12:00:00Z",
        "$orderby": "startDateTime desc",
    }).json().get("value", [])

    docs = []
    for ev in events:
        name = ev.get("eventName") or ev.get("agendaName") or "Meeting"
        # startDateTime is UTC; the local (Pacific) calendar date is what people expect.
        d = (datetime.fromisoformat(ev["startDateTime"].replace("Z", "+00:00")) - timedelta(hours=8)).date()
        for f in ev.get("publishedFiles") or []:
            kind = KINDS.get(f.get("type"), f.get("type") or "Document")
            if kind == "Agenda packet" and not ctx.packets:
                continue
            url = f"{api}/Meetings/GetMeetingFileStream(fileId={f['fileId']},plainText=false)"
            docs.append(MeetingDoc(name, d, url, kind))

    return scan_meeting_docs(cfg["name"], docs, ctx)
