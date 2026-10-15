# TRPA Mention Monitor

A single-page app showing where the Tahoe Regional Planning Agency (TRPA) comes up in
Lake Tahoe Region public meetings and press:

- **Coming up:** posted agendas for meetings that haven't happened yet
- **Meetings:** agendas, minutes, and packets from the past 30 days
- **Press:** news coverage from the past 30 days

TRPA Governing Board and Advisory Planning Commission (APC) meetings are excluded.

**Summary PDF:** the app's "Download summary (PDF)" button gets `data/TRPA_Mention_Summary.pdf`,
a printable brief built on every data refresh. It leads with upcoming meetings (key
passages and a link to the agenda page), then summarizes past meeting mentions and press
coverage. It uses Calibri 11 pt per the TRPA style guide. On a machine without Calibri it
falls back to Carlito (a Calibri-compatible font), then Helvetica.

**How it comes up:** each meeting mention is labelled by where it sits in the agenda
packet. The types are:

- **Agenda item:** a numbered item on the agenda. "Named in the item itself" means TRPA is in the item's own title.
- **Public comment:** letters, emails, written comments, or records requests from the public.
- **Staff report:** a staff report or memo, including letters attached to one.
- **Minutes:** minutes of an earlier meeting, included in the packet for approval.
- **Attachment:** another supporting document, such as a fee schedule or an agreement.

**Order:** upcoming meetings are listed soonest first in the app, calendar, and PDF, whether
TRPA or a keyword is an agenda item or appears in the packet. "How it comes up" labels each
one, but agenda items aren't ranked above other mentions. Each record still gets an
`importance` level in the table:

- **On the agenda:** TRPA or a keyword is part of an agendized item.
- **In meeting materials:** only in staff reports, attachments, or minutes.
- **Public comment only:** flagged as lower priority, shown muted, and listed last.

To change how contexts are ordered within a document, edit `PRIORITY` in
`trpa_monitor/classify.py`, then run `python -m trpa_monitor --rebuild`. That regenerates the app data, table, and PDF from the
last run without downloading anything again.

This is worked out from the document's structure (agenda pages, memo, email and minutes
headers) in `trpa_monitor/classify.py`, so treat it as a guide.

**Department keywords and views:** `keywords.csv` lists keywords by department, one row
per keyword:

```csv
department,keyword
Long Range,short-term rental
Long Range,workforce housing
Transportation,sidewalk
Transportation,bike path
```

Edit it in Excel or any text editor; a keyword can sit under more than one department.
Upcoming agendas and packets are searched for every keyword as well as TRPA. Matching
ignores capitalization and line breaks, matches whole words, and allows simple plurals.
Past meetings and press stay TRPA-only. For a one-off search, run
`python -m trpa_monitor --keyword "workforce housing"`.

The app's **Department view** picker lists each department in the CSV. Picking one filters
the cards, calendar, counts, and tables to upcoming meetings that match its keywords, plus
past meetings and press whose TRPA passages mention one of them. Its link
(`index.html?dept=Transportation`) opens straight to that view, so each department can bookmark
its own. The table's `departments` column records which departments' keywords matched.

New keywords are searched on the next full run. Moving keywords between departments or
renaming a department only needs `python -m trpa_monitor --rebuild`.

Meeting links in the app and the PDF open the agenda at the page of the first TRPA
mention (`#page=N`). IVGID's CivicClerk system only offers PDFs as downloads, so its
links name the page instead.

## How it works

Two parts:

| Part | What it does |
|---|---|
| `index.html` | The app. Calcite + Plotly + AG Grid with the TRPA brand tokens, per the `trpa-dashboard-stack` and `trpa-brand` skills. It reads `data/mentions.js`. |
| `trpa_monitor/` (Python) | The collector. It downloads agendas and press feeds, searches their text, and writes `data/mentions.json`, `data/mentions.js`, and `data/TRPA_Mention_Summary.pdf`. |

The collector is separate because a web page can't read these sources directly: almost
none of the agency sites or news feeds allow cross-origin requests from a browser, and
the agenda PDFs need server-side text extraction.

`data/mentions.js` holds the same data as `mentions.json`, wrapped in a script tag, so
`index.html` works when opened straight from disk as well as on GitHub Pages. Browsers
block `fetch()` of local files.

## Database-ready table

Every full run also writes `data/mentions_table.csv`: one row per matched document or
article, which are the same records the app lists. It's meant as the model for a future
database table that the app would read instead of `mentions.js`. `schema.sql` has the
matching `CREATE TABLE` with column notes, constraints, and indexes, plus optional child
tables if you want the JSON columns normalized.

- **Key:** `mention_id` is stable across runs (a hash of the document URL), so loads can upsert on it.
- **Columns:** plain fields cover filtering and sorting (`record_type`, `timing`, `event_date`,
  `agency`, `how_primary`, counts, `keyword_terms`). `contexts_json` and `passages_json` hold
  the "how it comes up" breakdown and passages the app renders.
- **Nulls:** empty cells mean NULL; treat `''` as NULL when loading.

## Updating the data

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m trpa_monitor
```

Or double-click `update_data.bat`. A full run takes about five minutes and rewrites
`data/`. Commit `data/` to publish the update.

### Daily updates

Agencies post agendas three to 10 days ahead, so refresh daily. `run_daily.bat` does an
unattended run (no window, no key press) and logs to `logs/update_YYYY-MM-DD.log`. To
schedule it with Windows Task Scheduler, run once in PowerShell from this folder:

```powershell
.\schedule_daily.ps1                 # every day at 6:00 a.m.
.\schedule_daily.ps1 -At 5:30am      # a different time
.\schedule_daily.ps1 -Publish        # also commit and push data/ so GitHub Pages updates
.\schedule_daily.ps1 -Remove         # stop the daily run
```

The task runs as you while you're logged on, and catches up if the computer was off or
asleep at the set time. `-Publish` commits only `data/` and pushes to whatever branch is
checked out, so use it on the branch GitHub Pages serves. The app warns when its data is
more than two days old.

Useful options:

```text
--days N        look back N days (default 30)
--ahead N       include agendas for meetings up to N days ahead (default 30)
--packets       scan full agenda packets for every agency (slower)
--only "Placer,Truckee"   test specific sources (does not update data/)
```

Partial runs (`--only`, `--meetings-only`, `--press-only`) don't touch `data/`, so the
app never shows a half-updated picture. If a source can't be reached during a full run,
its results from the previous run are kept and flagged in the app.

Some agency web hosts refuse Python's default connection while still serving browsers.
South Tahoe PUD and Tahoe RCD share such a host. For those, the collector automatically
retries with `curl_cffi`, which connects the way Chrome does.

## Sources

All sources are listed in `sources.toml`. There are 16 meeting sources (counties, the city
and town, utility, fire, and special districts, the Lahontan Water Board, and the
California Tahoe Conservancy) and nine press sources (Google News, Bing News, and local
outlet feeds). The app's "Sources checked" tab shows each source's status from the last run.

To add a source, see the comments at the top of `sources.toml`. Agency-specific scrapers
live in `trpa_monitor/sources/custom.py`, one short function per agency.

## Tuning

- **Search terms:** `patterns` in `sources.toml`.
- **Excluded meetings:** `exclude_meeting_patterns`.
- **Boilerplate to ignore:** `ignore_context_patterns`, for example the meeting-location
  line on Tahoe Transportation District agendas and "Sources: TRPA" credits on maps.
