-- TRPA Mention Monitor: model table for the web app's data source
--
-- data/mentions_table.csv is a snapshot of this table, rewritten by every collector run.
-- One row per matched document or article: an agenda, packet, or minutes that mentions
-- TRPA (or, for upcoming meetings, one of the keywords in keywords.csv), or a press item.
-- These are the same records the app lists.
--
-- Written for PostgreSQL. For SQL Server: TEXT -> NVARCHAR(MAX), BOOLEAN -> BIT,
-- TIMESTAMPTZ -> DATETIMEOFFSET, JSONB -> NVARCHAR(MAX) with ISJSON checks.
-- For SQLite: drop the CHECK constraints or keep them; types map to TEXT/INTEGER.
--
-- Loading a refresh: upsert on mention_id (stable across runs for the same document),
-- update collected_at, and leave rows from earlier runs in place if you want history.

CREATE TABLE mention (
    mention_id            TEXT PRIMARY KEY,       -- 16-hex-char SHA-1 of the document URL (without #page)
    collected_at          TIMESTAMPTZ NOT NULL,   -- when the collector run that produced the row finished (UTC)

    record_type           TEXT NOT NULL CHECK (record_type IN ('meeting', 'press')),
    timing                TEXT CHECK (timing IN ('upcoming', 'past')),  -- meetings only; NULL for press

    source_name           TEXT NOT NULL,          -- source in sources.toml: agency name, or "Google News", "Sierra Sun", ...
    source_platform       TEXT,                   -- Legistar, Granicus, CivicPlus AgendaCenter, RSS feed, ...
    agency                TEXT,                   -- meetings: the agency holding the meeting; NULL for press
    outlet                TEXT,                   -- press: the publication; NULL for meetings

    title                 TEXT NOT NULL,          -- meeting name, or press headline
    event_date            DATE,                   -- meeting date, or publication date
    document_type         TEXT,                   -- Agenda, Agenda packet, Minutes, Staff report: ..., Article

    url                   TEXT NOT NULL,          -- the document or article
    open_url              TEXT NOT NULL,          -- url plus #page=N to open the PDF at the first mention
    first_page            INTEGER,                -- page of the first mention (NULL for press / single-page docs)
    download_only         BOOLEAN NOT NULL,       -- true when the host serves the PDF only as a download (no page jump)

    trpa_mention_count    INTEGER NOT NULL DEFAULT 0 CHECK (trpa_mention_count >= 0),
    keyword_terms         TEXT,                   -- "; "-separated keywords matched (upcoming meetings only)
    keyword_mention_count INTEGER NOT NULL DEFAULT 0 CHECK (keyword_mention_count >= 0),
    departments           TEXT,                   -- "; "-separated departments (keywords.csv) whose keywords matched

    -- How the terms come up in the document (meetings only), from trpa_monitor/classify.py.
    -- importance labels each record in the app and PDF:
    --   agenda    = part of an agendized item (labelled, but not ranked above other mentions)
    --   materials = only in staff reports, attachments, or minutes
    --   public    = only in public comment or correspondence (lower priority)
    importance            TEXT CHECK (importance IN ('agenda', 'materials', 'public')),
    how_primary           TEXT CHECK (how_primary IN ('Agenda item', 'Staff report', 'Attachment',
                                                      'Minutes', 'Public comment')),  -- in priority order
    how_all               TEXT,                   -- "; "-separated distinct types, most significant first
    primary_item_title    TEXT,                   -- agenda item, staff report subject, letter, ...
    primary_item_pages    TEXT,                   -- ", "-separated pages for the primary context

    verified              BOOLEAN NOT NULL,       -- press: false = headline-level search hit, article text not checked
    key_passage           TEXT,                   -- first passage around a mention
    key_passage_page      INTEGER,
    carried_over          BOOLEAN NOT NULL DEFAULT FALSE,  -- source failed this run; row kept from the previous run

    -- Detail the app renders. Kept as JSON here; normalize into the child tables below if needed.
    contexts_json         JSONB NOT NULL DEFAULT '[]',  -- [{"type","title","pages":[..],"count","in_title"}]
    passages_json         JSONB NOT NULL DEFAULT '[]',  -- [{"term","page","text"}]

    CHECK ((record_type = 'meeting') = (timing IS NOT NULL)),
    CHECK ((record_type = 'meeting' AND agency IS NOT NULL AND outlet IS NULL)
        OR (record_type = 'press' AND outlet IS NOT NULL AND agency IS NULL))
);

-- The app's main queries: upcoming meetings by date, past meetings by date, press by date.
CREATE INDEX mention_timing_date_idx ON mention (record_type, timing, event_date);
CREATE INDEX mention_agency_idx      ON mention (agency);
CREATE INDEX mention_how_idx         ON mention (how_primary);
CREATE INDEX mention_importance_idx  ON mention (timing, importance, event_date);  -- "agenda items coming up"

-- Optional normalized children, if the JSON columns become limiting:
--
-- CREATE TABLE mention_context (
--     mention_id  TEXT REFERENCES mention (mention_id) ON DELETE CASCADE,
--     seq         INTEGER,            -- 0 = primary
--     type        TEXT,               -- Agenda item | Public comment | Staff report | Minutes | Attachment
--     title       TEXT,
--     pages       INTEGER[],
--     hit_count   INTEGER,
--     in_title    BOOLEAN,
--     PRIMARY KEY (mention_id, seq)
-- );
--
-- CREATE TABLE mention_passage (
--     mention_id  TEXT REFERENCES mention (mention_id) ON DELETE CASCADE,
--     seq         INTEGER,
--     term        TEXT,               -- 'TRPA' or the keyword
--     page        INTEGER,
--     text        TEXT,
--     PRIMARY KEY (mention_id, seq)
-- );
