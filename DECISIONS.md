# Decisions

Each entry: what I chose, why, and what I rejected.
(Draft carried over from planning. Rewrite these in your own words before submitting.)

## Repo
**D1 - .gitignore template: Python.**
Rejected: Node (not a JS project), Terraform (Azure hosting is described, not built),
none (would reinvent what the Python template already covers).

**D2 - No license.**
Rejected: MIT and others. A case submission doesn't need one and the work stays mine.
Note: the repo has to open without an invite, so make it public (or zip it) at submission.

**D-branch - The pivot to dbt + DuckDB is built on a `dbt-duckdb` branch.**
`main` keeps the earlier SQLite plan until the new version runs end to end, then gets merged.
Keeping the switch visible in the history shows a deliberate change of direction.
Rejected:
- rewriting main in place (hides the reasoning)
- a new repo (loses the history)

## Language
**D-lang - Python for ingestion (provisional).**
Still to decide properly. Alternatives considered: SQL only, Power Query,
PowerShell, Azure Data Factory.

## Storage and transformation
**D3 - Storage and transformation: DuckDB + dbt (revised 9 Nov).**
- First choice was SQLite + SQL views. I switched because:
  - dbt is SQL plus a little YAML, so Emil's SQL/Power BI team can own it
  - dbt tests catch duplicate ids and unexpected statuses
  - the same models can move to Fabric/Azure SQL via dbt adapters
- Raw appointments are appended as they come; dbt staging keeps the latest version
  per id, so the history of status changes isn't lost.
- Trade-offs I accept:
  - one more tool to install
  - DuckDB allows one writer at a time
  - QUALIFY isn't T-SQL, so the dedupe needs rewriting for Azure
- Rejected:
  - SQLite + views (simpler, but no tests, lineage or easy path to the warehouse)
  - Parquet as the primary store (rows change after the fact, e.g. status updates
    and cancellations; Parquet has no in-place updates and no SQL of its own)
  - CSV only
  - pandas in memory
  - Postgres or SQL Server in Docker (setup risk on the demo laptop)
  - Azure SQL directly (needs a cloud account, costs money)
- Production story: Azure SQL or Fabric, with Power BI on top.

## Tooling and repo structure
**D-python - Python 3.13 for the project venv (decided 9 Nov).**
dbt-duckdb does not install on Python 3.15: its dependency pyyaml has no ready-made package
for 3.15 yet, and building it needs Microsoft C++ Build Tools. 3.13 installs cleanly with
dbt-core 1.12.6, dbt-duckdb 1.11.1 and duckdb 2.0.0, and meets the 3.11+ requirement.
Installed with the Python install manager (`py install 3.13`); `.venv` rebuilt on it.
Rejected:
- staying on 3.15 and installing C++ Build Tools (~6 GB, more setup risk on the demo laptop,
  and other dbt dependencies could break next)
- the 3.10 already on the laptop (below the 3.11+ requirement)

**D-dbt-v1 - Stay on dbt Core v1 (pinned 1.12.6), not dbt v2.**
dbt now announces v2 as the default for new installations. dbt-duckdb is built for v1,
and nearly all documentation, examples and answers online are for v1, which is what
Emil's team will search for after handover. The models are plain SQL + YAML either way.
Rejected: dbt v2 (newer, but the adapter support and know-how are thinner; upgrading later
is a documented path).

**D-lint - ruff for formatting and linting.**
One fast tool instead of three.
Rejected: black + flake8 + isort (same job, more setup), no linter (inconsistent code at handover).

**D-profiles - dbt profiles.yml committed in the repo.**
DuckDB needs no credentials, so there's nothing secret in it, and a fresh clone runs
with no extra setup.
Rejected: the dbt default of `~/.dbt/profiles.yml` (a reviewer or Emil wouldn't have it,
so the first run would fail).

**D-entry - One entry point, `run_pipeline.py` (ingest, then `dbt build`).**
One command for the live demo and for whoever schedules it later.
Rejected:
- Makefile (awkward on Windows, which Nordvet's IT likely uses)
- Airflow/Dagster/Prefect (far too heavy for one daily job)
- separate manual steps (easy to run out of order)

**D-tests - dbt tests are the only automated tests for this slice.**
- unique + not_null on keys
- accepted_values on status
- relationships from appointments to clinics
These check the data itself, which is where problems will come from.
Rejected for now: pytest on the Python code (useful, but lower priority than data checks
in a 4-5 hour slice; it's on the next-steps list).

**D-config - Settings and credentials from environment variables (.env + python-dotenv).**
.env.example ships with placeholders only.
Rejected:
- hard-coded values (credentials would leak into git)
- a YAML config file (one more thing to explain for a handful of settings)
- Azure Key Vault (right for production, overkill on a laptop; it's in the Azure story)

**D-logging - Python logging module, with row counts and run time per step.**
Rejected: print statements (can't be filtered or sent to Azure Monitor later).

**D-structure - Flat, small repo: `ingestion/`, `nordvet_dbt/`, `data/` (gitignored), docs at root.**
The structure mirrors the flow, so Emil can find things.
Rejected:
- a `src/` package layout with setup.py/pyproject packaging (it's a pipeline, not a library)
- a separate repo for dbt (two repos for a two-person team)

## Frequency
**D-batch - Daily batch, not real-time.**
Mette's question is about yesterday, every morning. Real-time adds cost and
running complexity for a two-person IT team, and the API is slow to wake up.

## Metric
**D-formula - no-show rate = no_show / (completed + no_show).**
Cancelled appointments are excluded, because a cancelled slot isn't a no-show.

**D-metric - Unresolved past `booked` rows.**
Yesterday is shown per clinic as confirmed no-shows plus a separate
"awaiting status" count. The headline clinic ranking uses a rate over settled days.
The lower/upper range is kept as two columns.

**D-settled - The last 3 days count as unsettled.**
They are left out of the clinic-ranking rate.

**D-fields - patient_ref and vet_id not stored; updated_at, cancelled_at, deleted_at and created_at kept.**
`patient_ref` and `vet_id` are dropped in Python before loading, so they never reach disk.
`created_at` is kept although nothing uses it yet: it is cheap and allows a later
lead-time analysis (how far ahead was the booking made, and do late bookings no-show more?).

## Findings
**D-findings - FINDINGS.md short list for Mette.**
No slides, and no Power BI report unless time allows.
Parquet/CSV only as an optional export of the final view for Power BI.

## Ingestion
**D-deleted - Always request `include_deleted=true`; keep `deleted_at`; drop deleted rows in staging.**
Without the flag, deleted appointments silently disappear from the API. Raw is append-only,
so a row loaded before it was deleted would otherwise stay in the counts forever.
With the flag, deleted rows come back with a `deleted_at` timestamp and a normal-looking status.
Staging keeps the latest version per id first, then drops rows where `deleted_at` is set.
Evidence (9 Nov): default pull 5,442 rows; same pull with the flag 5,496, of which 53 had `deleted_at`.
Only `true`/`True` work; `1` or `yes` are silently ignored (200 OK, no deleted rows).
Rejected:
- not sending the flag (deleted appointments would be counted as real no-shows/completions)
- dropping deleted rows in Python before loading (raw should hold what the API said; staging decides)
- a periodic full reload to catch deletions (heavier on the API, and the flag makes it unnecessary)

**D-backfill - `limit=500`; first run is a one-off backfill with `from` and `to` always sent together.**
500 is the API's real maximum: higher values are silently capped at 500 (default is 100),
so 500 means the fewest calls without relying on undocumented behaviour.
`from` and `to` are both needed because leaving one out changes the window a lot:
`to` alone returns all history back to 31 Jul 2026; `from` alone runs a month into future bookings.
Both dates are inclusive. Assumed to be the clinic's local date, but not tested: appointments
run 08:00-17:15 local, so the local and UTC dates are always the same and the data can't
tell them apart. Doesn't affect results today (see Next steps).
Backfill start date: 1 Sep 2026 (set as `BACKFILL_FROM` in .env), to the run date + 90 days.
Note on "90 days": here it means 90 days *ahead* (future bookings), not 90 days of history.
History is set by the start date (1 Sep). An earlier plan suggested "90 days of history";
that was replaced by the fixed 1 Sep start.
This gives a 9-week baseline, matching the SQLite-era choice. History starts 31 Jul 2026,
but the extra month adds calls for little gain.
Why end 90 days ahead (changed 9 Nov, was "to the run date"): a booking made before the
backfill for a future date, and never changed afterwards, would never come back through
`updated_since`, so it would be missing from the "awaiting status" count. With the window
reaching past every existing booking (the API showed bookings ~30 days ahead), every
appointment is either in the backfill or created after it, and so caught incrementally.
The run logs a warning if bookings reach the last day of the window.
Rejected:
- `limit=1000` or higher (works, but only because it is quietly capped; misleading to read)
- the default limit of 100 (5x more calls on a rate-limited API)
- open-ended `from` or `to` (unpredictable size; one test pulled 60,000 rows by accident)
- keeping the backfill "to the run date" (simpler, but the awaiting-status count can miss
  old bookings that were never updated)

**D-incremental - Daily run uses `updated_since` = the highest `updated_at` already in raw.**
The watermark is read from the data, not from the clock or a "last run" record, so a failed
run is simply picked up again by the next one, and laptop/API clock differences don't matter.
`updated_since` ignores the default 7-day window, so late status changes on older appointments
are caught (9 Nov: rows scheduled 28 Oct returned because their status changed on 2 Nov).
The boundary is inclusive and `updated_at` is mostly whole minutes, so each run re-fetches a
few rows it already has. That is safe: raw is append-only and staging keeps one row per id.
Missing a row would be worse than fetching it twice, so no attempt to shave off the overlap.
Rejected:
- a fixed re-pull window, e.g. last 14 days (misses changes to older appointments, more calls)
- a full reload every day (about 60,000 rows and hundreds of calls)
- a separate "last run" table (one more thing to maintain; the data already holds the answer)
- starting one second after the watermark (could miss rows written in that same minute)

**D-validate - Python checks its own request parameters before calling the API.**
The API accepts some bad input with 200 OK and quietly returns the wrong thing:
- `from` after `to` -> 0 rows, no error (the run would "succeed" with an empty day)
- `include_deleted=1` or `yes` -> flag ignored (deleted rows would go missing)
- `to` without `from` -> all history (a daily run could turn into a 60,000-row pull)
- `limit` above 500 -> silently capped
So: `include_deleted` is hard-coded to the string "true" in one place; `from` <= `to` and
"both or neither" are checked before calling; a backfill returning 0 rows logs a warning.
Plain `if` statements that fail with a clear message.
Rejected:
- trusting the API to reject bad input (it doesn't in these cases)
- a validation library such as pydantic (too much to explain for three or four checks)

**D-errors - Match the response to the error type.**
- Token: fetch a fresh one at the start of each run, and again on a 401, then retry that call once.
  Tokens last exactly 60 minutes (decoded from the token's `exp`); the token response doesn't say so.
  A daily run fits easily; only the first backfill could cross the hour. Only one retry, because
  a second 401 means the problem isn't expiry (e.g. a rotated secret), and repeated logins could
  lock the account.
- 429: wait exactly the `Retry-After` seconds, then retry. Seen values: 1-12 seconds during
  exploration, 51 seconds once during the first backfill. Gives up after 20 waits in a row for
  one call, so a permanently throttled API fails the run instead of waiting forever.
- 500 ("temporary error, please retry"): retry up to 4 times with 2/4/8/16s pauses, then fail
  loudly and leave the previous data as it was. About 1 in 15 calls hit one on 9 Nov; all
  succeeded on retry.
- Network errors and timeouts (no response at all, e.g. the API waking up): treated like a 500,
  same 4 retries and pauses.
- Other 4xx: never retry; the request itself is wrong, so fail at once with the message.
One small function with a loop, no retry framework.
Rejected:
- refreshing early by reading `exp` (relies on an undocumented token format)
- treating 429 like other 4xx and failing (broke the SQLite-era history pull)
- tenacity / urllib3 Retry (extra dependency, harder for Emil's team to read)

**D-atomic - Each pull is loaded all-or-nothing, in one transaction.**
All pages are collected first, then inserted in a single transaction. A crash or API failure
mid-pull leaves raw exactly as it was.
Why: the backfill comes back sorted by `scheduled_at`, not `updated_at`. If half a backfill
were saved, the next run would take its watermark from that half and silently skip the older
appointments it never fetched. "Raw only ever holds complete pulls" keeps the watermark
trustworthy. About 50,000 rows fit easily in memory.
Cost: rows are inserted with a plain `executemany`. The first backfill (50,474 rows) took
about 47s to insert, out of 117s for the whole run; daily runs (a few hundred rows) take
under a second. Accepted for now because it is the simplest code to read.
Rejected:
- saving page by page and resuming (needs a separate progress record; more to explain and maintain)

**D-metadata - Every raw row gets `_loaded_at` and `_run_id`.**
Shows which run loaded which rows ("this run loaded X rows"), and helps trace a bad load.
Cheap: two columns.
Rejected: no metadata (simpler, but rows can't be traced back to a run).

**D-clinics - Clinics are re-fetched every run and appended to `raw_clinics`, not overwritten.**
The raw layer is append-only for every table (CLAUDE.md), so clinics follow the same rule as
appointments. Each run adds one full snapshot (39 rows) with `_run_id` and `_loaded_at`;
staging takes the latest snapshot. It also keeps a history of clinic changes (e.g. a clinic
going inactive) at a cost of 39 rows a day.
Rejected: overwriting the clinics table each run (simpler to query, but breaks the append-only
rule and loses when a clinic changed).

## dbt models
**D-materialization - Staging models are views; marts are tables.**
Staging is a thin cleanup over raw, so a view always shows the latest raw rows and costs
nothing to store. Marts are what Power BI and Mette read, so they are built once per run as
tables: fast to query, and a stable copy if a later run fails halfway.
Rejected:
- everything as tables (duplicates raw in staging for no gain at this size)
- everything as views (Power BI would re-run the whole chain on every refresh)
- incremental models (not needed at ~50,000 rows; full rebuild takes under a second)

**D-stg-clinics - `stg_vetone__clinics` takes the newest snapshot by `_run_id`.**
`_run_id` is the run's UTC start time (e.g. 20261109T130505Z), so the highest one is the
latest load. Inactive clinics are kept in staging; the marts decide whether to show them.
Rejected: latest row per clinic id across all snapshots (would keep a clinic that VetOne
has removed entirely).

**D-dedupe - `stg_vetone__appointments` keeps the latest version per id, then drops deleted.**
`qualify row_number() over (partition by id order by updated_at desc, _loaded_at desc) = 1`.
`_loaded_at` breaks ties when the same version was fetched twice (the inclusive watermark
overlap, D-incremental). Dedupe happens *before* the deleted filter: if an appointment is
deleted after we loaded it, its newest version is the deleted one, so it disappears. Filtering
first would let the older, non-deleted version win and stay in the counts.
Checked 9 Nov: 50,530 raw rows -> 50,489 ids -> 49,787 after removing 702 deleted;
identical to the same logic recomputed in Python, 0 status mismatches.
Rejected:
- deduping in Python before loading (raw would lose the history of status changes)
- filtering deleted rows before deduping (resurrects deleted appointments, see above)
- `select distinct` (keeps every version whose status differs)

**D-timestamps - Cast to `timestamptz` with the dbt session in UTC; keep the local date as text gives it.**
- All timestamps are cast to `timestamptz`, never `timestamp`, which silently drops the
  offset (see Tooling notes). `profiles.yml` sets the session timezone to UTC.
- `scheduled_date_local` = the first 10 characters of `scheduled_at` (e.g. 2026-11-05).
  The API already sends the clinic's local time, so its date part *is* the clinic's day.
  This is the "day" for all reporting ("yesterday per clinic").
- `scheduled_at_local` = local wall-clock time (e.g. 08:00), for time-of-day views.
Rejected: converting UTC back through each clinic's timezone (needs a join to clinics and
gives the same answer, since VetOne already sends local time).

**D-test-severity - Unknown `service` values warn; unknown `status` values fail the run.**
Status drives the no-show metric, so an unexpected status must stop the run before Mette
sees wrong numbers. A new service type doesn't change the metric, so it should be noticed
(a warning in the run log) without blocking the morning report.
Rejected: failing on both (a harmless new service would block the report); no service test.

## API quirks found
Found during the API exploration on 9 Nov 2026. Raw responses are saved in `data/explore/`
(gitignored, so local only).

1. **Deleted appointments are hidden by default.** Default 7-day pull: 5,442 rows; with
   `include_deleted=true`: 5,496, of which 53 had a `deleted_at` field. Deleted rows keep a
   normal status (e.g. `completed`). `deleted_at` is never after `updated_at`. -> D-deleted
2. **`include_deleted` silently ignores values it doesn't recognise.** `true`/`True` work;
   `1`/`yes` return 200 with no deleted rows. -> D-validate
3. **`updated_since` drops the default 7-day window.** It returned appointments from 28 Oct
   (late status changes) and future bookings to 9 Dec. -> D-incremental
4. **`updated_since` includes the boundary; `updated_at` is mostly whole minutes** (4,576 of
   5,442 end in `:00`). Rows stamped exactly at the watermark come back again. -> D-incremental
5. **`updated_since` timezones:** `Z`, `+01:00`, `-05:00` and no offset give identical results
   (no offset = UTC). An unencoded `+` gets `400 invalid updated_since`. A bare date is
   accepted as midnight UTC.
6. **Leaving out `from` or `to` changes the window a lot.** No params: 7 days back to today.
   `from` only: open-ended into future bookings. `to` only: all history from 31 Jul 2026.
   `from` after `to`: 200 with 0 rows. Dates are inclusive; a datetime gets a 400.
   -> D-backfill, D-validate
7. **`limit` is silently capped at 500.** Default 100; 0, -1 and text get a 400. -> D-backfill
8. **The cursor carries its own filters.** It is signed base64 JSON (filters, an as-of
   timestamp, sort key `scheduled_at` + `id`). Filters sent with a cursor are ignored; an
   edited cursor gets `400 invalid cursor`. No duplicate ids within any full pull.
9. **Tokens last 60 minutes**, but the token response only has `access_token` and
   `token_type`; the expiry is inside the token itself. -> D-errors
10. **Transient errors.** About 1 in 15 calls got `500 temporary error, please retry` (all
    succeeded on retry). Paging at ~3 requests/s triggered 429s with `Retry-After` of 1-12s.
    -> D-errors
11. **39 clinics, not 38 as the brief says.** 38 are active; the 39th is CL-420 Nordvet Ystad
    (SE), marked `active: false`, with appointments until September and none since. 24 DK,
    15 SE. Clinics have 7 fields: `id`, `name`, `city`, `country`, `timezone`
    (Europe/Copenhagen or Europe/Stockholm), `active`, `opened_on`. `/v1/clinics` is one page
    (no `next_cursor`). -> D-clinics; inactive clinic handling to decide in the marts.

Tooling notes (not the API, but found while building):
- **DuckDB `cast(... as timestamp)` silently drops the UTC offset.**
  `cast('2026-11-09T13:28:00+01:00' as timestamp)` gives 13:28, not 12:28 UTC. Casting to
  `timestamptz` (with the session timezone set to UTC) converts correctly. Staging must use
  `timestamptz` for `scheduled_at`, `updated_at`, `cancelled_at`, `deleted_at`, `created_at`.

Data quality on 74,238 rows (Jul-Dec): no nulls in key fields, only the 4 known statuses,
no unknown clinic ids, `cancelled_at` set exactly when cancelled, `scheduled_at` offsets switch
correctly at the 25 Oct clock change, duration is fixed per service. Inactive CL-420 (Ystad)
had appointments until September.

## Next steps / what I'd change with more time
Candidates (Claude's suggestions: keep, edit or delete):
- Run it on a schedule in Azure (e.g. Container Apps job or Azure Function) instead of my laptop
- Move the models to Fabric Warehouse or Azure SQL (T-SQL has no QUALIFY, so the dedupe needs rewriting)
- Build a Power BI report on the final view for Mette
- Test whether `from`/`to` mean the clinic's local date or UTC (needs an appointment near
  midnight, e.g. an emergency/out-of-hours clinic; matters only if opening hours change)
- Add alerting when a clinic's no-show rate spikes
- Lead-time analysis using `created_at`: do bookings made far ahead (or last minute) no-show more?
- Add pytest for the API client (pagination, token expiry) and run checks in GitHub Actions
- Faster raw insert for big backfills (e.g. DuckDB reading a temporary JSON/Parquet file
  instead of `executemany`), if the 47s backfill insert ever matters