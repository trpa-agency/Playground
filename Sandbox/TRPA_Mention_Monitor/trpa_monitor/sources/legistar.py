"""Legistar Web API (https://webapi.legistar.com/Help)."""
import logging
from datetime import datetime

from ..fetch import get
from . import Context, MeetingDoc, scan_meeting_docs

log = logging.getLogger(__name__)
API = "https://webapi.legistar.com/v1/{client}"


def run(cfg: dict, ctx: Context):
    api = API.format(client=cfg["client"])
    w = ctx.meeting_window
    events = get(f"{api}/events", params={
        "$filter": f"EventDate ge datetime'{w.start:%Y-%m-%d}' and EventDate le datetime'{w.end:%Y-%m-%d}'",
        "$orderby": "EventDate desc",
    }).json()

    docs: list[MeetingDoc] = []
    for ev in events:
        body = ev.get("EventBodyName") or "Meeting"
        if ctx.meeting_excluded(body):
            continue
        d = datetime.fromisoformat(ev["EventDate"]).date()
        page = ev.get("EventInSiteURL") or ""
        if ev.get("EventAgendaFile"):
            docs.append(MeetingDoc(body, d, ev["EventAgendaFile"], "Agenda"))
        if ev.get("EventMinutesFile"):
            docs.append(MeetingDoc(body, d, ev["EventMinutesFile"], "Minutes"))

        # Item titles cover meetings with no agenda PDF; item attachments are the staff reports.
        if ev.get("EventAgendaFile") and not ctx.packets:
            continue
        try:
            items = get(f"{api}/events/{ev['EventId']}/eventitems",
                        params={"AgendaNote": 1, "MinutesNote": 1, "Attachments": int(ctx.packets)}).json()
        except Exception as e:
            log.warning("%s: event items for %s failed: %s", cfg["name"], ev["EventId"], e)
            continue
        text = "\n".join(
            " ".join(filter(None, [i.get("EventItemAgendaNumber"), i.get("EventItemTitle"),
                                   i.get("EventItemAgendaNote"), i.get("EventItemMinutesNote"),
                                   i.get("EventItemActionText")]))
            for i in items)
        if not ev.get("EventAgendaFile"):
            docs.append(MeetingDoc(body, d, page or api, "Agenda items", text=text))
        if ctx.packets:
            for i in items:
                for a in i.get("EventItemMatterAttachments") or []:
                    if a.get("MatterAttachmentHyperlink"):
                        docs.append(MeetingDoc(body, d, a["MatterAttachmentHyperlink"],
                                               f"Attachment: {a.get('MatterAttachmentName', '')}"[:120]))

    return scan_meeting_docs(cfg["name"], docs, ctx)
