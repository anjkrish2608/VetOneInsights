# Decisions

Each entry: what I chose, why, and what I rejected.
(Draft carried over from planning. Rewrite these in your own words before submitting.)

## Repo
**D1 - .gitignore template: Python.** Hosted on GitHub.
Rejected: Node (not a JS project), Terraform (Azure hosting is described, not built),
none (would reinvent what the Python template already covers).
Added on top: `data/` (API pulls and the database: the brief asks for no data dumps), `.env`,
`*.duckdb`, `*.db`, `*.sqlite` and `*.pdf` (the case brief contains the client secret).
Change if: reviewers need a small sample file, in which case add an exception for that one file.

**D2 - No license.**
Rejected: MIT and others. A case submission doesn't need one and the work stays mine.
Note: the repo has to open without an invite, so make it public (or zip it) at submission.

**D-branch - The pivot to dbt + DuckDB is built on a `dbt-duckdb` branch.**
`main` keeps the earlier SQLite plan until the new version runs end to end, then gets merged.
Keeping the switch visible in the history shows a deliberate change of direction.
Merged into `main` on 9 Nov 2026, once the pipeline ran end to end from a clean start, with a
merge commit (`--no-ff`) so the `dbt-duckdb` branch stays visible as one block in the history.
Rejected:
- rewriting main in place (hides the reasoning)
- a new repo (loses the history)
- a fast-forward merge (possible, since main hadn't moved, but the pivot would blend into
  main's history with no marker of where the branch began and ended)

## Language
**D-lang - Python for ingestion (decided 9 Nov; was provisional).**
Python handles only the API part: login, paging, retries, token refresh and appending raw rows.
Everything after that is SQL in dbt. dbt has no way to call an API, so something has to do
this step. In Python it is about 200 lines of plain functions that Emil's team can read, and
it is built and tested against the live API (backfill, incremental runs, failure paths).
Rejected:
- SQL only (can't page through an API, refresh tokens or retry errors)
- Power Query (tied to a Power BI refresh; can't append to a raw table or handle retries
  the way this API needs)
- PowerShell (less common in data teams; clumsier JSON handling)
- Azure Data Factory (needs a cloud account and costs money for a laptop demo; a fair
  production option for Nordvet, covered in the README's Azure section)

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
  - upserting by appointment id, only when the incoming `updated_at` is newer (the SQLite-era
    load; it worked and was safe to re-run, but overwrites each row, so the history of status
    changes is lost and there's nothing for dbt tests to check against)
- Note: the SQLite-era log rejected DuckDB as "an extra tool with no clear gain at this size".
  dbt changed that: dbt-duckdb gives tests and lineage with nothing to install beyond pip.
- Production story: Azure SQL or Fabric, with Power BI on top (D-azure).

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
No-shows are recorded about a day late (D-settled), so real-time would only show wrong
numbers faster. It's also cheaper, which matters for Karin's cost test.
Rejected: real-time or streaming (Anders, Head of Digital, asked for it; it adds cost and no
usable accuracy for this question).
Change if: Nordvet adds a use case that acts within the hour, such as reassigning a vet when
a patient doesn't arrive.

## Metric
**D-formula - no-show rate = no_show / (completed + no_show).**
Cancelled appointments are excluded, because a cancelled slot isn't a no-show.

**D-metric - Unresolved past `booked` rows.**
Yesterday is shown per clinic as confirmed no-shows plus a separate
"awaiting status" count. The headline clinic ranking uses a rate over settled days.
The lower/upper range is kept as two columns:
- lower = no_show / (completed + no_show + awaiting): every awaiting appointment turns out completed
- upper = (no_show + awaiting) / (completed + no_show + awaiting): every awaiting one is a no-show
Why: statuses are finalised at different speeds (see D-settled). Completions are recorded
within hours, but no-shows about a day later, so at 8am yesterday's no-shows are mostly still
`booked`. Evidence (SQLite era, 6 Nov): 241 past appointments were still `booked`, 81 of them
from earlier days (2-5 Nov: 3, 2, 20, 56), with more unresolved the more recent the day. For
5 Nov at 8am: 13 confirmed no-shows and 56 still booked, i.e. 1.8% confirmed vs 8.9% if every
unresolved booking became a no-show. A rate for yesterday alone would mislead Mette; counts that
can be read at a glance would not. Settled days give a stable ranking.
Rejected:
- counting unresolved bookings as no-shows (overstates: most turn out completed)
- ignoring them (understates, and hides the gap)
- a range as the only view (too wide on a single day to tell clinics apart)
Change if: Mette would rather wait a few days for final numbers, or VetOne offers a faster
way to record no-shows.

**D-settled - The last 3 days count as unsettled.**
They are left out of the clinic-ranking rate.
Precisely: a day is settled when `days_ago > 3` (as of today, Mon 9 Nov: 5 Nov and earlier).
In practice the earliest settled day is read about 3.5-4 days after its appointments.
The 3 is a dbt variable (`unsettled_days` in dbt_project.yml), so it can be raised without
touching SQL if more history shows no-shows arrive later.
Why 3 - how long after the appointment each status is recorded (`updated_at` - `scheduled_at`):

| Status | SQLite era, 7-day window (6 Nov) | Re-measured 9 Nov, Sep-Oct appointments |
|---|---|---|
| completed | median 2.0h, 90% within 3.2h | median 2.0h, 90% within 3.2h (99.6% within 3 days) |
| no_show | min 15.1h, median 25.2h, 90% within 53.6h, max 117.2h | min 14.8h, median 25.4h, 90% within 66.5h, max 126.3h |
| cancelled | median 20.8h *before* start, 90% by 2.1h after | median 20.5h before start, 90% by 2.9h after, max 5.0h after |

The SQLite-era window was only 7 days, so slow no-shows fell outside it ("censored") and the
lag looked shorter (90% within ~2.2 days). With 9 weeks of data: 92.3% of no-shows are
recorded within 3 days and 96.1% within 4.
Supporting evidence: no `booked` rows are left for any September day (checked in the SQLite era
and again 9 Nov), and on 9 Nov only 3 appointments on settled days were still awaiting a status.
Known limit: a few no-shows arrive later (the slowest took about 5 days), so the ranking
slightly understates every clinic's rate.
Is the lag equal across clinics? (open in the SQLite era, checked 9 Nov) Not exactly: the share
of no-shows recorded within 3 days ranges from 82.5% (Jönköping) to 100% across the 38 active
clinics; the slowest are Jönköping, Odense S, Esbjerg, Aarhus C and Hellerup. Within 4 days,
every clinic is at 93% or more. Small clinics have few no-shows (42-70 at the slowest), so part
of the spread is noise, and it barely correlates with the no-show rate (-0.2). The bias could
move a clinic's rate by a few tenths of a point, not change the ranking, where the gaps between
best and worst are 15+ points.
Change if: more history shows the lag getting longer, or a clinic's late recording grows; then
raise `unsettled_days` to 4.
Rejected: 1 day (40% of no-shows recorded) or 2 days (81%), measured 9 Nov; 7 days (100%
recorded, but the ranking would lag a week behind for about 4 points more completeness).

**D-last-open-day - Mette's "yesterday" is the last day any clinic was open (decided 9 Nov).**
Clinics are closed on Sundays, so on Mondays calendar yesterday has no appointments and the
view would be empty. `is_last_open_day` marks the most recent day before today with any
appointments across the network: Saturday on a Monday, the previous day otherwise, and it
skips public holidays without a holiday calendar. A clinic with no appointments that day
simply has no row.
Rejected: strict calendar yesterday (`days_ago = 1`): empty every Monday and after holidays.

**D-ranking-window - Two windows: the recent 28 settled days (ranked), and all settled history.**
- Recent: the newest 28 settled days (days_ago 4 to 31). The rank uses this, so it reflects
  what is happening now and Mette can act on it. About 25 appointments per clinic per day
  gives several hundred per clinic, enough for a stable rate.
- History: every settled day since `BACKFILL_FROM` (1 Sep), as a baseline, so a clinic whose
  recent rate jumps can be compared with its own normal.
- Each window shows its counts (no-shows, completed) next to the rate, so a small sample is
  visible, plus the network rate and the clinic's gap to it in percentage points.
- 28 is a dbt variable (`ranking_window_days`).
Rejected: only the recent window (no baseline); only history (reacts slowly to change).

**D-inactive - Inactive clinics are left out of the ranking but keep their daily history.**
CL-420 Ystad stays in the daily mart with `is_active = false` (its September data is real)
and is filtered out of the ranking. `is_active` comes from the latest clinic snapshot, so:
- a clinic VetOne marks inactive tomorrow drops out of the ranking on the next run, with no
  code change; its history stays, flagged. The flag shows status *now*, not on that day.
- `raw_clinics` keeps every snapshot (D-clinics), so the run where it changed is on record.
- a clinic removed from VetOne entirely fails the `relationships` test (appointments ->
  clinics), so the run stops loudly instead of silently dropping its appointments.
- a new clinic appears automatically.
Rejected: dropping inactive clinics everywhere (loses real history); ranking them (a closed
clinic in Mette's list is noise).

**D-money - Money lost = booked vet minutes lost to no-shows (`duration_minutes`), not kroner.**
VetOne has no prices or fees, so Karin's "where are we losing money" is measured in vet time:
the booked minutes of every no-show. Shown in minutes and hours per clinic-day and per clinic.
Turning it into kroner needs Nordvet's average revenue per vet hour; that's a single
multiplication once they give it to us.
Rejected: guessing a price per service (would present made-up kroner as fact).

**D-late-cancellations - Late cancellations stay "cancelled" for now; flagged to discuss with Nordvet.**
Late-recorded cancellations *are* picked up: cancelling sets `updated_at` equal to
`cancelled_at` (all 3,782 cancelled rows), so the next run fetches the change and the marts
recalculate. They arrive within hours (latest 5h), well inside the 3-day settled rule.
The open question is what they mean: 766 of 3,782 cancellations (20%) were recorded *after*
the appointment had started (median 2.8h, 90% within 4.6h). These are probably "the patient
didn't come and reception marked it cancelled", i.e. no-shows in practice. Counting them would
raise no-shows from 3,474 to about 4,240 (+22%).
Decision: keep the fixed metric (cancelled excluded) and leave them out for this first slice.
This goes beyond what was asked, and changing the definition is Nordvet's call, not ours.
To discuss with Mette, then possibly add later (see Next steps).
Rejected for now:
- counting them as no-shows (changes the agreed metric without the client)
- adding a `late_cancellations` column now (useful, but not requested; better built once
  Nordvet has said what a late cancellation means)

**D-fields - patient_ref and vet_id not stored; updated_at, cancelled_at, deleted_at and created_at kept.**
`patient_ref` and `vet_id` are dropped in Python before loading, so they never reach disk.
`created_at` is kept although nothing uses it yet: it is cheap and allows a later
lead-time analysis (how far ahead was the booking made, and do late bookings no-show more?).
Why not `patient_ref`: it's patient-related, and a clinic-level no-show view doesn't need it.
Why not `vet_id`: vet-level reporting is out of scope for Mette's question.
Change if: Nordvet wants vet-level reporting, or wants to dig into an outlier clinic (e.g. is
Aarhus C's 24% driven by one vet's diary?). Then add `vet_id` to the loader and re-run the
backfill; `patient_ref` should stay out unless there's a clear, agreed purpose.

## Findings
**D-findings - FINDINGS.md short list for Mette.**
No slides, and no Power BI report unless time allows.
Parquet/CSV only as an optional export of the final view for Power BI.

**D-azure - Production target: Container Apps Job + Key Vault + Azure SQL Database + Power BI.**
Described in the README, not built (decided 9 Nov).
- Azure SQL Database (Basic, about $5/month): Emil's team already knows SQL Server tools,
  Power BI connects natively, and the data is tiny (tens of MB). The dbt models move with the
  `dbt-sqlserver` adapter; `qualify`, `timezone()`, `strftime` and `datediff` need T-SQL
  rewrites, and the raw loader switches from DuckDB to an Azure SQL connection.
- Container Apps Job: runs the unchanged `python run_pipeline.py` daily. A 2-minute run uses
  about 1% of the free monthly grant (180,000 vCPU-seconds), so about $0.
- Key Vault for the VetOne credentials, passed in as environment variables (no code change).
- Prices checked by web search on 9 Nov 2026 (list prices, USD): Azure SQL Basic about $5/month
  (up to ~$20 by region), Power BI Pro $14/user/month (raised from $10 in 2025; included in
  Microsoft 365 E5). Infrastructure total about $5-25/month.
Rejected:
- DuckDB file on Azure storage with marts exported as Parquet (cheapest, no SQL rewrite, but
  Power BI reads files rather than a database and it is less familiar to Emil's team)
- Microsoft Fabric (only sensible if Nordvet already pays for Fabric capacity)
- Azure Functions (a timer trigger works, but running dbt inside Functions is awkward; the job
  runs the same command as the laptop)
- Azure Data Factory for the extract (heavier than one API call loop; a fair no-code option)

**D-docs - dbt docs is how people browse the models (documented in the README, not hosted).**
`dbt docs generate` + `dbt docs serve` build a local website from the same YAML descriptions
and tests the pipeline uses: every model, column and test, plus the lineage graph from raw to
marts. The documentation can't drift from the code, and there's no separate wiki to maintain.
Run it after a pipeline run (DuckDB allows one writer at a time). Tested 9 Nov.
Rejected for now: hosting the docs as a static site in Azure (small next step); a hand-written
data dictionary (would go out of date).

**D-images - Screenshots live in `docs/images/` (folder added 9 Nov, approved).**
Two PNGs taken from `dbt docs`: the lineage graph (raw -> staging -> marts) and the daily
mart's documentation page. GitHub shows them inline in the README. Terminal output is shown as
a text block from a real run instead of an image, so it can be read and copied.
Rejected: videos committed to the repo (large files); screenshots of the run output (text is
clearer); embedding images from outside the repo (could break later).

**D-findings-snapshot - FINDINGS.md is frozen at Mon 9 Nov 2026 (run 20261109T135405Z).**
The data is live, so numbers re-run later drift as statuses change. The header states the
as-of date and load time, and the appendix gives the `as_of_date` command plus the SQL behind
every number, so they can be traced. In the interview a fresh live run shows "today" next to it.
Rejected: regenerating it on interview day (fresher, but the text would need checking again).

**D-morning-sample - Morning view sample: the 5 clinics with the most no-shows, sorted by count.**
On a single day the numbers are too small to rank clinics by rate: on Sat 7 Nov, 27 of 38
clinics had 0 no-shows (a "best 3" would be an arbitrary pick from a tie), and the highest
rates were 1 no-show out of 3 appointments (33%). Sorting by number of no-shows (then awaiting
status) answers "who needs a call today?". The 3 worst + 3 best comparison goes in the
ranking finding instead, where 28 settled days give several hundred appointments per clinic.
Rejected: 3 worst + 3 best by rate on one day (noise); all 38 clinics (too long for a summary).

**D-fte - Lost vet hours are also shown as full-time vets, assuming a 37-hour week.**
525 hours in 28 days / 4 weeks = 131 hours a week; / 37 hours = about 3.5 full-time vets.
Worded as "the equivalent of about 3.5 full-time vets' booked time".
Assumptions: 37 hours is the standard Danish full-time week (Sweden's is 40, giving 3.3, so
"about 3.5" still holds); it counts booked appointment time only, not admin or breaks.
Rejected: hours only (accurate, but less meaningful to Karin at a glance).

**D-findings-staging - Service and weekday findings are queried outside the marts for now.**
Findings 4 (service) and 5 (weekday) come from SQL on staging and the daily mart, written out in
the FINDINGS.md appendix. They are the most actionable findings (where reminders pay off), so
they are included even though no mart holds them yet.
With more time: a mart for them, so they are built and tested every run (see Next steps).
Rejected: leaving them out (loses the clearest "what to do"); building a mart now (more work
than two numbers justify in this slice).

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
Lesson learned (SQLite era): the first history pull stopped after one page, reported success,
and was 7 weeks short. The API was fine: probing four filter combinations (from/to, no `to`, a
different start date, a smaller `limit`) all returned a `next_cursor`. The bug was a missing
line in my own loop that read the cursor from each response. A pull that quietly returns too
little is worse than one that fails, so today's code guards against it:
- every pull logs how many pages and rows it fetched, and why it stopped (no `next_cursor`)
- paging stops with an error at 1,000 pages instead of looping forever
- a backfill returning 0 rows logs a warning; so does one whose bookings reach the window's end
- the dbt test `assert_daily_mart_reconciles_to_staging` catches rows lost between layers
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
- Timeout: 60 seconds per request. The API scales to zero when idle, so the first call of a
  run can take about 20 seconds while it wakes up; 60 leaves room without hanging forever.
  (Flagged "needs explanation" in the SQLite-era log.)
- SQLite-era full history pull, for comparison: 4 rate limits with `Retry-After` of 20, 19, 2
  and 1 seconds, and 3 transient 500s, all fine on the first retry. That run is where "wait
  for the header, not a fixed pause" came from.
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
So "a day" runs midnight to midnight in each clinic's own time. The API gives every clinic a
timezone (Europe/Copenhagen or Europe/Stockholm); both share the same clock, and the offsets
switch correctly at the 25 Oct clock change (summer and winter both checked).
Change if: Mette wants one company-wide cut-off time instead.

**D-test-severity - Unknown `service` values warn; unknown `status` values fail the run.**
Status drives the no-show metric, so an unexpected status must stop the run before Mette
sees wrong numbers. A new service type doesn't change the metric, so it should be noticed
(a warning in the run log) without blocking the morning report.
Rejected: failing on both (a harmless new service would block the report); no service test.

**D-marts - Two mart tables, at two grains.**
- `mart_clinic_daily_noshows`: one row per clinic per local day, every day before the as-of
  date. Mette's morning view (`is_last_open_day`) and Power BI trends both come from it.
- `mart_clinic_noshow_ranking`: one row per active clinic, built *from the daily mart*, so the
  as-of date and the settled rule are defined once.
SQL uses `sum(case when ...)` rather than DuckDB's `filter` / `count_if`, so the marts move
to Azure SQL / Fabric with few changes.
Rejected:
- a separate "yesterday" table (a filter on the daily mart does it; one less model to keep in step)
- one wide table with both grains (mixes daily rows and clinic totals; easy to double-count)
- doing the ranking in Power BI only (the logic would live outside SQL, untested)

**D-as-of - "Today" is a dbt variable, defaulting to today's date in Copenhagen.**
`as_of_date` defaults to `cast(timezone('Europe/Copenhagen', current_timestamp) as date)`;
`dbt build --vars "{as_of_date: '2026-11-06'}"` rebuilds the marts as of any past morning.
Both countries share Copenhagen's clock time. Used to reproduce FINDINGS.md numbers, to
demo, and to re-run a past day. Checked 9 Nov: as of 6 Nov, the last open day is Thu 5 Nov
and settled days end on 2 Nov.
Rejected: plain `current_date` (it's the UTC date in our session, a day behind Copenhagen
between midnight and 01:00/02:00).

**D-singular-tests - Three SQL test files in `nordvet_dbt/tests/` (folder added 9 Nov, approved).**
- `assert_noshow_rates_between_0_and_1`: every rate in both marts is between 0 and 1
- `assert_noshow_rate_bounds_ordered`: lower <= confirmed <= upper on every clinic-day
- `assert_daily_mart_reconciles_to_staging`: per day, the mart's appointment total equals the
  staging count, so no appointment is lost or double-counted between layers
Each returns the offending rows, so a failure shows exactly what's wrong. Checked 9 Nov:
`dbt build` passes 40/40 (4 models, 36 tests); daily mart and ranking spot-checked against
raw/staging by hand.
Rejected: the `dbt_utils` package (a dependency for two or three checks; plain SQL is
easier for Emil's team to read).

**D-dbt-run - `run_pipeline.py` runs `dbt build` as a subprocess after ingestion.**
`dbt build` runs every model and every test in dependency order, so one command both builds
and checks the data. It's the same command Emil's team would type themselves. It runs only
after ingestion has closed its DuckDB connection (DuckDB allows one writer). The dbt next to
the running Python is used, so the venv's pinned version runs even if the venv isn't
activated. If dbt fails, the run exits with code 1; this run's raw rows stay loaded (raw is
append-only and correct), so after fixing the cause a plain re-run finishes the job.
Rejected:
- dbt's Python API (`dbtRunner`): less familiar to a SQL team than the command line
- `dbt run` then `dbt test` separately: a bad staging model would feed the marts before tests run
- separate manual steps (easy to run out of order; D-entry)

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
    (no `next_cursor`), with no duplicate ids. -> D-clinics, D-inactive
12. **Response shape and timestamp formats** (first seen in the SQLite era). Records sit under
    a `data` key, not at the top level, with `next_cursor` next to it. `scheduled_at` is the
    clinic's local time with an offset and no seconds (`2026-11-05T08:00+01:00`);
    `created_at`, `updated_at`, `cancelled_at` and `deleted_at` are UTC with `Z`
    (`2026-10-29T12:27:41Z`). -> D-timestamps

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
- Check what Nordvet's Power BI licence includes before promising Mette a subscription email:
  subscriptions and sharing need Pro (or Premium Per User / capacity). Not verified yet.
- Re-check the no-show recording lag per clinic as history grows (D-settled): Jönköping is
  slowest today (82.5% within 3 days); raise `unsettled_days` if that gets worse
- Vet-level view for outlier clinics (D-fields): add `vet_id` if Nordvet wants it
- Add alerting when a clinic's no-show rate spikes
- A mart for no-shows by service and weekday (D-findings-staging), so FINDINGS.md findings
  4 and 5 are built and tested every run instead of queried by hand
- Late cancellations (D-late-cancellations): discuss with Mette whether a cancellation
  recorded after the appointment started is really a no-show; then add a separate
  `late_cancellations` count to the daily mart, or fold them into the rate if Nordvet agrees
- Lead-time analysis using `created_at`: do bookings made far ahead (or last minute) no-show more?
- Add pytest for the API client (pagination, token expiry) and run checks in GitHub Actions
- Faster raw insert for big backfills (e.g. DuckDB reading a temporary JSON/Parquet file
  instead of `executemany`), if the 47s backfill insert ever matters