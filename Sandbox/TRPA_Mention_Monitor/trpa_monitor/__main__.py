"""Command-line entry point:  python -m trpa_monitor [options]"""
import argparse
import json
import logging
import re
import sys
import tomllib
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

from .classify import sort_contexts
from .matcher import Matcher, flatten_keywords, keyword_pattern, load_departments
from .models import Mention, Window
from .report import (dedupe_press, table_rows, write_app_data, write_csv, write_html, write_json,
                     write_mentions_table)
from .sources import SCAN_STATS, Context, get_adapter
from .summary_pdf import write_summary_pdf

ROOT = Path(__file__).resolve().parent.parent


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="trpa_monitor",
        description="Flag mentions of the Tahoe Regional Planning Agency (TRPA) in Lake Tahoe "
                    "public meetings (excluding TRPA Governing Board/APC) and press.")
    p.add_argument("--days", type=int, default=30, help="look back this many days (default 30)")
    p.add_argument("--since", type=date.fromisoformat, help="start date YYYY-MM-DD (overrides --days)")
    p.add_argument("--until", type=date.fromisoformat, help="end date YYYY-MM-DD (default today)")
    p.add_argument("--ahead", type=int, default=30,
                   help="also check agendas already posted for meetings up to this many days "
                        "after the end date (default 30; 0 = past meetings only)")
    p.add_argument("--config", type=Path, default=ROOT / "sources.toml")
    p.add_argument("--out", type=Path, default=ROOT / "output", help="output folder")
    p.add_argument("--only", help="comma-separated source names to run (substring match)")
    p.add_argument("--meetings-only", action="store_true")
    p.add_argument("--press-only", action="store_true")
    p.add_argument("--packets", action="store_true",
                   help="also scan full agenda packets / staff reports (much slower, more thorough)")
    p.add_argument("--no-cache", action="store_true", help="re-download documents")
    p.add_argument("--app-data", type=Path, default=ROOT / "data",
                   help="folder for the web app's data files (mentions.json and mentions.js)")
    p.add_argument("--keywords-file", type=Path, default=ROOT / "keywords.csv",
                   help="department keywords to search for in upcoming meetings "
                        "(CSV with department and keyword columns)")
    p.add_argument("--keyword", action="append", default=[], metavar="PHRASE",
                   help="add an extra keyword for this run only (repeatable)")
    p.add_argument("--rebuild", action="store_true",
                   help="regenerate the app data, table, and summary PDF from the last run's data/mentions.json "
                        "without downloading anything (after changing display or classification settings)")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def rebuild(app_data: Path, config: Path, keywords_file: Path) -> int:
    """Rewrite app data, table, and PDF from the previous run's results (no fetching)."""
    d = json.loads((app_data / "mentions.json").read_text(encoding="utf-8"))
    mentions = []
    for m in d["mentions"]:
        fields = {k: v for k, v in m.items() if k in Mention.__dataclass_fields__}
        mention = Mention(**{**fields, "date": date.fromisoformat(m["date"]) if m.get("date") else None})
        mention.contexts = sort_contexts(mention.contexts)
        mentions.append(mention)
    window = Window(date.fromisoformat(d["window"]["start"]), date.fromisoformat(d["window"]["end"]))
    meeting_window = Window(window.start, date.fromisoformat(d["meeting_window"]["end"]))
    keywords, status = d.get("keywords", []), d.get("sources", [])
    # Department groupings come from the current keywords.csv, so regrouping keywords needs no
    # new download. Keywords added since the last run only take effect after a full run.
    departments = load_departments(keywords_file) or d.get("departments", {})
    write_app_data(app_data, mentions, window, meeting_window, status, keywords, d["generated_at"], departments)
    cfg = tomllib.loads(config.read_text(encoding="utf-8"))
    platforms = {s["name"]: PLATFORMS.get(s["type"], s["type"]) for s in cfg.get("source", [])}
    carried = {s["name"] for s in status if s.get("previous_run")}
    write_mentions_table(app_data / "mentions_table.csv",
                         table_rows(mentions, d["generated_at"], platforms, carried, departments))
    generated = datetime.fromisoformat(d["generated_at"]).astimezone().replace(tzinfo=None)
    write_summary_pdf(app_data / "TRPA_Mention_Summary.pdf", mentions, window, meeting_window, status,
                      generated, keywords=keywords, departments=departments)
    print(f"Rebuilt app data, table, and summary PDF from the run of {d['generated_at']} ({len(mentions)} records).")
    return 0


def carry_over(app_data: Path, failed: set[str], window: Window, meeting_window: Window) -> tuple[list, str]:
    """Previous run's results for sources that failed this time, so a temporary outage
    doesn't drop them from the app. Returns (mentions, previous run timestamp)."""
    path = app_data / "mentions.json"
    if not failed or not path.exists():
        return [], ""
    prev = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for m in prev.get("mentions", []):
        if m["source"] not in failed or not m.get("date"):
            continue
        fields = {k: v for k, v in m.items() if k in Mention.__dataclass_fields__}
        mention = Mention(**{**fields, "date": date.fromisoformat(m["date"])})
        if mention.category == "press":
            keep = window.contains(mention.date)
        else:
            keep = meeting_window.contains(mention.date)
            mention.category = "meeting"  # re-derived below against today's date
        if keep:
            out.append(mention)
    return out, prev.get("generated_at", "")


PRESS_TYPES = {"google_news", "bing_news", "rss"}
PLATFORMS = {
    "google_news": "Google News search", "bing_news": "Bing News search", "rss": "RSS feed",
    "legistar": "Legistar", "granicus": "Granicus", "municode": "Municode Meetings",
    "civicplus": "CivicPlus AgendaCenter", "civicclerk": "CivicClerk",
    "ntpud": "Agency website", "ttd": "Agency website", "lahontan": "Agency website",
    "tahoe_conservancy": "Agency website", "streamline": "Agency website",
    "pdf_links": "Agency website", "ntfire": "Agency website",
}


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.rebuild:
        return rebuild(args.app_data, args.config, args.keywords_file)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(message)s")
    logging.getLogger("pypdf").setLevel(logging.ERROR)  # noisy font warnings on odd PDFs
    cfg = tomllib.loads(args.config.read_text(encoding="utf-8"))
    settings = cfg.get("settings", {})

    end = args.until or date.today()
    window = Window(args.since or end - timedelta(days=args.days), end)
    matcher = Matcher(settings["patterns"], settings.get("ignore_context_patterns", []))
    ctx = Context(
        window=window,
        meeting_window=Window(window.start, end + timedelta(days=args.ahead)),
        matcher=matcher,
        exclude_meetings=[re.compile(p, re.I) for p in settings.get("exclude_meeting_patterns", [])],
        exclude_domains=[d.lower() for d in settings.get("exclude_domains", [])],
        packets=args.packets,
        use_cache=not args.no_cache,
    )
    departments = load_departments(args.keywords_file)
    keywords = flatten_keywords(departments)
    for kw in args.keyword:
        if kw.lower() not in {k.lower() for k in keywords}:
            keywords.append(kw)
    ctx.keywords = {kw: Matcher([keyword_pattern(kw)]) for kw in keywords}

    sources = [s for s in cfg.get("source", []) if s.get("enabled", True)]
    if args.only:
        wanted = [w.strip().lower() for w in args.only.split(",")]
        sources = [s for s in sources if any(w in s["name"].lower() for w in wanted)]
    if args.meetings_only:
        sources = [s for s in sources if s["type"] not in PRESS_TYPES]
    if args.press_only:
        sources = [s for s in sources if s["type"] in PRESS_TYPES]

    print(f"Searching {len(sources)} sources for TRPA mentions, {window.start} to {window.end}"
          + (f" (plus meetings through {ctx.meeting_window.end})" if args.ahead else ""))
    if keywords and args.ahead:
        print("Upcoming meetings also searched for: " + ", ".join(keywords))
    print()
    mentions, errors, status = [], {}, []
    for s in sources:
        print(f"  {s['name']:<38}", end="", flush=True)
        row = {"name": s["name"], "kind": "press" if s["type"] in PRESS_TYPES else "meetings",
               "platform": PLATFORMS.get(s["type"], s["type"]), "hits": 0, "ok": True, "error": ""}
        try:
            src_ctx = replace(ctx, packets=True) if s.get("packets") else ctx
            found = get_adapter(s["type"])(s, src_ctx)
            mentions += found
            row["hits"] = len(found)
            stats = SCAN_STATS.get(s["name"])
            if stats:
                row.update(docs_scanned=stats["scanned"], docs_unreadable=stats["unreadable"])
            print(f"{len(found):>3} hit(s)" + (f"  ({stats['unreadable']} of {stats['scanned']} documents unreadable)"
                                               if stats and stats["unreadable"] else ""))
        except Exception as e:
            errors[s["name"]] = f"{type(e).__name__}: {e}"
            row.update(ok=False, error=errors[s["name"]][:300])
            print("  FAILED -", errors[s["name"]][:90])
        status.append(row)

    full_run = not (args.only or args.meetings_only or args.press_only)
    if full_run and args.app_data and errors:
        carried, prev_time = carry_over(args.app_data, set(errors), window, ctx.meeting_window)
        mentions += carried
        for row in status:
            if not row["ok"]:
                row["carried_over"] = sum(1 for m in carried if m.source == row["name"])
                row["previous_run"] = prev_time
        if carried:
            print(f"\nKept {len(carried)} result(s) from the previous run for sources that failed.")

    press = dedupe_press([m for m in mentions if m.category == "press"])
    meetings = [m for m in mentions if m.category == "meeting"]
    for m in meetings:
        if m.date and m.date > end:
            m.category = "upcoming"
    upcoming = [m for m in meetings if m.category == "upcoming"]
    mentions = meetings + press

    args.out.mkdir(parents=True, exist_ok=True)
    stem = args.out / f"trpa_mentions_{window.start}_{window.end}"
    write_csv(stem.with_suffix(".csv"), mentions)
    write_json(stem.with_suffix(".json"), mentions, window, errors)
    write_html(stem.with_suffix(".html"), mentions, window, errors, matcher.regex, ctx.meeting_window.end)
    # A partial run would wipe the other sources' results from the app, so only full runs update it.
    if args.app_data and full_run:
        write_app_data(args.app_data, mentions, window, ctx.meeting_window, status, keywords,
                       departments=departments)
        # Database-style table (model for the app's eventual data source; see schema.sql).
        generated_at = json.loads((args.app_data / "mentions.json").read_text(encoding="utf-8"))["generated_at"]
        platforms = {s["name"]: PLATFORMS.get(s["type"], s["type"]) for s in sources}
        carried_names = {r["name"] for r in status if r.get("previous_run")}
        write_mentions_table(args.app_data / "mentions_table.csv",
                             table_rows(mentions, generated_at, platforms, carried_names, departments))
        try:
            write_summary_pdf(args.app_data / "TRPA_Mention_Summary.pdf", mentions, window,
                              ctx.meeting_window, status, keywords=keywords, departments=departments)
        except Exception as e:  # the app data is still good without the PDF
            print(f"\nWARNING: summary PDF not written: {type(e).__name__}: {e}")

    print(f"\n{len(upcoming)} upcoming meeting document(s), {len(meetings) - len(upcoming)} past "
          f"meeting document(s) and {len(press)} press item(s) match.")
    order = {"upcoming": 2, "meeting": 1, "press": 0}
    for m in sorted(mentions, key=lambda m: (order[m.category], str(m.date)), reverse=True):
        flag = "" if m.verified else " [unverified]"
        terms = (["TRPA"] if m.hit_count else []) + list(m.keywords)
        how = f" [{m.contexts[0]['type']}]" if m.contexts else ""
        print(f"  {m.date}  {m.category:<8} {m.source} | {m.title[:60]} ({m.detail}){how}{flag}"
              + (f"  terms: {', '.join(terms)}" if m.keywords else ""))
    print(f"\nReport: {stem.with_suffix('.html')}\n        {stem.with_suffix('.csv')}")
    return 1 if errors and not mentions else 0


if __name__ == "__main__":
    sys.exit(main())
