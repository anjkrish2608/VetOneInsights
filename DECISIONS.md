# Decisions

Each entry: what I chose, why, and what I rejected.

**Format:** 
- **Decision** = the bold title line (what I chose)
- **Context** = why: the situation and evidence, linked to [docs/vetone_api_notes.md](docs/vetone_api_notes.md) where it came from the API
- **Rejected** = the options I considered and why not
- **Consequences** = what the choice costs ("Trade-offs:") and what would reopen it ("Change if:")
- **Status** = Accepted unless the entry says "changed" (with a date) or "superseded"

## Contents

- [Repo](#repo): D1, D2, D-branch
- [Language](#language): D-lang
- [Storage and transformation](#storage-and-transformation): D3
- [Tooling and repo structure](#tooling-and-repo-structure): D-python, D-dbt-v1, D-lint, D-profiles, D-entry, D-tests, D-config, D-logging, D-structure, D-docs
- [Frequency](#frequency): D-batch
- [Ingestion](#ingestion): D-deleted, D-page-size, D-backfill, D-incremental, D-validate, D-errors, D-api-change, D-atomic, D-metadata, D-clinics
- [dbt models](#dbt-models): D-materialization, D-stg-clinics, D-dedupe, D-timestamps, D-test-severity, D-marts, D-as-of, D-singular-tests, D-analyses, D-dbt-run
- [Metric](#metric): D-formula, D-metric, D-settled, D-last-open-day, D-ranking-window, D-inactive, D-money, D-late-cancellations, D-fields
- [Findings](#findings): D-findings, D-findings-snapshot, D-morning-sample, D-fte, D-findings-staging
- [Production (Azure)](#production-azure): D-azure, D-pricing
- [API observations](#api-observations)
- [Next steps / what I'd change with more time](#next-steps--what-id-change-with-more-time)

## Repo

**D1 - .gitignore template: Python.** Hosted on GitHub.

Rejected:
- **Node:** Not a JS project.
- **Terraform:** Azure hosting is described, not built.
- **No template:** Would reinvent what the Python template already covers.

Added on top: `data/` (API pulls and the database: the brief asks for no data dumps), `.env`, `*.duckdb`, `*.db`, `*.sqlite` and `*.pdf` (the case brief contains the client secret).

Change if: reviewers need a small sample file, in which case add an exception for that one file.

**D2 - No license.**

Rejected: **MIT and others.** A case submission doesn't need one and the work stays mine.

Note: the repo has to open without an invite, so make it public (or zip it) at submission.

Trade-offs: others can read the code but have no right to reuse it.

Change if: Nordvet or Heyra want to reuse the code; then agree a licence.

**D-branch - The pivot to dbt + DuckDB was built on a `dbt-duckdb` branch, then merged into `main`.**

`main` kept the SQLite plan until the new version ran end to end. On 9 Nov the branch was merged with a merge commit (`--no-ff`), so the switch stays visible as one block in the history.

Rejected:
- **Rewriting `main` in place:** Hides the reasoning.
- **A new repo:** Loses the history.
- **A fast-forward merge:** The pivot would blend into `main` with no marker of where it began and ended.

Trade-offs: two merge commits in `main`'s history.

Change if: nothing; the merge is done.

## Language

**D-lang - Python for ingestion (decided 9 Nov; was provisional).**

Python handles only the API part (login, paging, retries, appending raw rows); everything after that is SQL in dbt, because dbt can't call an API. It's about 200 lines of plain functions that Emil's team can read.

Rejected:
- **SQL only:** Can't page through an API, refresh tokens or retry errors.
- **Power Query:** Tied to a Power BI refresh; can't append to a raw table or handle retries the way this API needs.
- **PowerShell:** Less common in data teams; clumsier JSON handling.
- **Azure Data Factory:** Needs a cloud account and costs money for a laptop demo; a fair production option (D-azure).

Trade-offs: two languages for the team to maintain (Python and SQL).

Change if: Nordvet prefers a no-code extract, e.g. Azure Data Factory.

## Storage and transformation

**D3 - Storage and transformation: DuckDB + dbt (revised 9 Nov).**
- First choice was SQLite + SQL views. I switched because:
  - dbt is SQL plus a little YAML, so Emil's SQL/Power BI team can own it
  - dbt tests catch duplicate ids and unexpected statuses
  - the same models can move to Fabric/Azure SQL via dbt adapters
- Raw appointments are appended as they come; dbt staging keeps the latest version per id, so the history of status changes isn't lost.
- Trade-offs I accept:
  - one more tool to install
  - DuckDB allows one writer at a time
  - QUALIFY isn't T-SQL, so the dedupe needs rewriting for Azure
- Rejected:
  - **SQLite + views:** Simpler, but no tests, lineage or easy path to the warehouse.
  - **Parquet as the primary store:** Rows change after the fact, e.g. status updates and cancellations; Parquet has no in-place updates and no SQL of its own.
  - CSV only
  - pandas in memory
  - **Postgres or SQL Server in Docker:** Setup risk on the demo laptop.
  - **Azure SQL directly:** Needs a cloud account, costs money.
  - **Upserting by appointment id, only when the incoming `updated_at` is newer:** The SQLite-era load; it worked and was safe to re-run, but overwrites each row, so the history of status changes is lost and there's nothing for dbt tests to check against.
- Note: the SQLite-era log rejected DuckDB as "an extra tool with no clear gain at this size". dbt changed that: dbt-duckdb gives tests and lineage with nothing to install beyond pip.
- Production story: Azure SQL or Fabric, with Power BI on top (D-azure).

## Tooling and repo structure

**D-python - Python 3.13 for the project venv (decided 9 Nov).**

dbt-duckdb doesn't install on Python 3.15 yet: one of its dependencies needs a C++ compiler there. 3.13 installs cleanly with the pinned packages and meets the 3.11+ requirement.

Rejected:
- **Staying on 3.15 and installing C++ Build Tools:** ~6 GB, more setup risk on the demo laptop, and other dbt dependencies could break next.
- **The 3.10 already on the laptop:** Below the 3.11+ requirement.

Trade-offs: the project needs a specific Python version installed.

Change if: dbt supports Python 3.15; then upgrade.

**D-dbt-v1 - Stay on dbt Core v1 (pinned 1.12.6), not dbt v2.**

dbt now announces v2 as the default for new installations. dbt-duckdb is built for v1, and nearly all documentation, examples and answers online are for v1, which is what Emil's team will search for after handover. The models are plain SQL + YAML either way.

Rejected:
- **dbt v2:** Newer, but the adapter support and know-how are thinner; upgrading later is a documented path.

Trade-offs: it will need upgrading to v2 eventually.

Change if: dbt-duckdb and dbt-sqlserver support v2 well.

**D-lint - ruff for formatting and linting.**

One tool instead of three: `ruff format` does black's job, and `ruff check` does flake8's and isort's. It's fast enough never to be skipped, and gives Emil's team one consistent style.

Rejected:
- **Black + flake8 + isort:** The same job as ruff, with more setup.
- **No linter:** Inconsistent code at handover.

Trade-offs: there's no ruff config file, so the rules are the pinned version's defaults; upgrading ruff can change them.

Change if: Nordvet's team has its own Python style standard, or wants stricter or looser rules; then add a small `[tool.ruff]` config and commit it.

**D-profiles - dbt profiles.yml committed in the repo.**

DuckDB needs no credentials, so there's nothing secret in it, and a fresh clone runs with no extra setup.

Rejected:
- **The dbt default of `~/.dbt/profiles.yml`:** A reviewer or Emil wouldn't have it, so the first run would fail.

Trade-offs: the local database path is in the repo (harmless, no secrets).

Change if: moving to Azure SQL; then read the connection from environment variables and never commit it.

**D-entry - One entry point, `run_pipeline.py` (ingest, then `dbt build`).**

One command for the live demo and for whoever schedules it later.

Rejected:
- **Makefile:** Awkward on Windows, which Nordvet's IT likely uses.
- **Airflow/Dagster/Prefect:** Far too heavy for one daily job.
- **Separate manual steps:** Easy to run out of order.

Trade-offs: one script to maintain, with no scheduling built in.

Change if: more jobs or dependencies between jobs appear; then use a scheduler or orchestrator.

**D-tests - dbt tests are the only automated tests for this slice.**

Evidence: API note [17](docs/vetone_api_notes.md#17-data-quality-is-clean).
- unique + not_null on keys
- accepted_values on status
- relationships from appointments to clinics

These check the data itself, which is where problems will come from.

Rejected for now: **pytest on the Python code**. These are useful, but lower priority than data checks in time frame, added to developments list.

Trade-offs: bugs in the Python code only show up as data problems.

Change if: the ingestion code grows or changes often; then add pytest.

**D-config - Settings and credentials from environment variables (.env + python-dotenv).**

.env.example ships with placeholders only.

Rejected:
- **Hard-coded values:** Credentials would leak into git.
- **A YAML config file:** One more thing to explain for a handful of settings.
- **Azure Key Vault:** Right for production, overkill on a laptop; it's in the Azure story.

Trade-offs: each machine needs its own `.env`.

Change if: it runs in production; then Key Vault supplies the same variables.

**D-logging - Python logging module, with row counts and run time per step.**

Why: CLAUDE.md asks for rows fetched, rows loaded and time taken; log levels (INFO/WARNING/ERROR) make a failed or suspicious run stand out; and the same lines can go to Azure Monitor in production.

Rejected:
- **Print statements:** No levels, can't be filtered or sent to Azure Monitor later.
- **A logging library such as structlog:** One more dependency for one script.

Trade-offs: logs go to the console only; nothing is kept on the laptop.

Change if: it runs in Azure, where the job's console output is collected by Azure Monitor.

**D-structure - Flat, small repo: `ingestion/`, `nordvet_dbt/`, `data/` (gitignored), `docs/`.**

The structure mirrors the flow, so Emil can find things. Documentation is split by the question each file answers: README (how to run it), DECISIONS.md (why), docs/vetone_api_notes.md (what we found), FINDINGS.md (results for Mette), and docs/history (the SQLite-era log).

Rejected:
- **A `src/` package layout with setup.py/pyproject packaging:** It's a pipeline, not a library.
- **A separate repo for dbt:** Two repos for a two-person team.
- **One big DECISIONS.md holding observations too:** It reached 600+ lines and mixed facts with choices.
- **Leaving DECISIONS_v1.md at the root:** Two decision logs side by side invites reading the old one.

Trade-offs: documentation is spread over several files that must stay in step.

Change if: the team finds the split confusing.

**D-docs - dbt docs is how people browse the models (documented in the README, not hosted).**

`dbt docs generate` and `dbt docs serve` build a local website from the same descriptions and tests the pipeline uses, including the lineage graph, so the documentation can't drift from the code. Run it after a pipeline run.

Rejected for now:
- **Hosting the docs as a static site in Azure:** Small next step.
- **A hand-written data dictionary:** Would go out of date.

Trade-offs: the docs only exist on the laptop of whoever generates them.

Change if: more people need them; then host them as a static site.


## Frequency

**D-batch - Daily batch, not real-time.**

Mette's question is about yesterday, each morning. No-shows are recorded late (D-settled), so real-time would only show wrong numbers faster, and it would add cost and running work for a two-person team.

Rejected:
- **Real-time or streaming:** Anders, Head of Digital, asked for it; it adds cost and no usable accuracy for this question.

Trade-offs: the numbers are always a day behind, by design.

Change if: Nordvet adds a use case that acts within the hour, such as reassigning a vet when a patient doesn't arrive.

## Ingestion

**D-deleted - Always request `include_deleted=true`; keep `deleted_at`; drop deleted rows in staging.**

Evidence: API note [1](docs/vetone_api_notes.md#1-deleted-appointments-are-hidden-by-default).

Without the flag, deleted appointments silently disappear from the API, and because raw is append-only, a row loaded before it was deleted would stay in the counts forever. With the flag they come back with `deleted_at`, and staging drops them after keeping the latest version per id.

Rejected:
- **Not sending the flag:** Deleted appointments would be counted as real no-shows/completions.
- **Dropping deleted rows in Python before loading:** Raw should hold what the API said; staging decides.
- **A periodic full reload to catch deletions:** Heavier on the API, and the flag makes it unnecessary.

Trade-offs: raw keeps deleted rows, so slightly more storage.

Change if: VetOne changes how deletes are flagged (D-api-change).

**D-page-size - Request 500 appointments per page.**

Evidence: API note [7](docs/vetone_api_notes.md#7-limit-is-silently-capped-at-500).

500 is the API's real maximum: anything higher is silently capped at 500, and the default is 100. So 500 means the fewest calls without relying on undocumented behaviour.

Rejected:
- **`limit=1000` or higher:** Works only because it's quietly capped, so it misleads anyone reading the code.
- **The default of 100:** Five times more calls on a rate-limited API.

Trade-offs: relies on the cap staying at 500.

Change if: VetOne raises or lowers the cap.

**D-backfill - The first run backfills from 1 Sep 2026 to the run date + 90 days.**

Evidence: API notes [6](docs/vetone_api_notes.md#6-leaving-out-from-or-to-changes-the-window-a-lot), [18](docs/vetone_api_notes.md#18-calendar-facts).

- **Start 1 Sep** (`BACKFILL_FROM`): gives a settled 9-week baseline. This is roughly 1,300 appoitnments per clinic, allowing a steady average to be drawn.
- **End 90 days *ahead* (future bookings, not history):** existing future bookings are fetched once. Otherwise a booking made before the backfill, and never changed afterwards, would never come back through `updated_since` and would be missing from "awaiting status". Bookings reach about 30 days ahead, and the run warns if they reach the end of the window.

Status: changed 9 Nov (the window used to end on the run date).

Rejected:
- **Keeping the backfill to the run date:** Misses old future bookings that never change.
- **An open-ended `from` or `to`:** Unpredictable size; one test pulled 60,000 rows by accident (D-validate).

Trade-offs: the first run takes about 2 minutes, mostly waiting on rate limits.

Change if: the history start date or the booking horizon changes.

**D-incremental - Daily run uses `updated_since` = the highest `updated_at` already in raw.**

Evidence: API notes [3](docs/vetone_api_notes.md#3-updated_since-drops-the-default-7-day-window), [4](docs/vetone_api_notes.md#4-updated_since-includes-the-boundary-and-updated_at-is-mostly-whole-minutes).

The starting point comes from the data, not the clock or a "last run" record, so a failed run is simply picked up by the next one. `updated_since` ignores the default 7-day window, so late status changes on older appointments are caught. The boundary is inclusive, so a few rows come back twice; staging dedupes them, and fetching a row twice is safer than missing one.

Rejected:
- **A fixed re-pull window, e.g. the last 14 days:** Misses changes to older appointments, and makes more calls.
- **A full reload every day:** About 60,000 rows and hundreds of calls.
- **A separate "last run" table:** One more thing to maintain; the data already holds the answer.
- **Starting one second after the watermark:** Could miss rows written in that same minute.

Trade-offs: a few rows are re-fetched every run (harmless).

Change if: `updated_since` proves unreliable; then add the weekly cross-check.

**D-validate - Python checks its own request parameters before calling the API.**

Evidence: API notes [2](docs/vetone_api_notes.md#2-include_deleted-silently-ignores-values-it-doesnt-recognise), [5](docs/vetone_api_notes.md#5-updated_since-timezone-handling), [6](docs/vetone_api_notes.md#6-leaving-out-from-or-to-changes-the-window-a-lot).

The API accepts some bad input with 200 OK and quietly returns the wrong thing: `from` after `to` gives 0 rows, `include_deleted=1` is ignored, and `to` without `from` returns all history. So `include_deleted` is hard-coded to the string "true", and `from` ≤ `to` and "both or neither" are checked before calling, with plain `if` statements that fail with a clear message.

Lesson learned (SQLite era): the first history pull stopped after one page, reported success and was 7 weeks short, because of a bug in my own paging loop. So every pull now logs its pages, rows and why it stopped; paging stops with an error at 1,000 pages; and a backfill that looks too small logs a warning.

Rejected:
- **Trusting the API to reject bad input:** It doesn't in these cases.
- **A validation library such as pydantic:** Too much to explain for three or four checks.

Trade-offs: a few checks to keep in step with the API.

Change if: VetOne fixes its silent behaviours or publishes a versioned API.

**D-errors - Match the response to the error type.**

Evidence: API notes [9](docs/vetone_api_notes.md#9-tokens-last-60-minutes-but-the-token-response-doesnt-say-so), [10](docs/vetone_api_notes.md#10-transient-errors-and-rate-limits), [13](docs/vetone_api_notes.md#13-the-first-call-is-slow).

- **Token:** a fresh one at the start of each run. On a 401, get one new token and retry once; a second 401 means something else is wrong (e.g. a rotated secret), and repeated logins could lock the account.
- **429 (rate limited):** wait exactly the `Retry-After` time, up to 20 times in a row.
- **500, network errors and timeouts:** retry up to 4 times with 2, 4, 8 and 16 second pauses, then fail.
- **Other 4xx:** fail at once; the request itself is wrong.
- **Timeout:** 60 seconds per request, because the API can take about 20 seconds to wake up.

One small function with a loop, no retry framework.

Rejected:
- **Refreshing the token early by reading its `exp`:** Relies on an undocumented token format.
- **Treating 429 like other 4xx and failing:** That broke the SQLite-era history pull.
- **Tenacity / urllib3 Retry:** An extra dependency, harder for Emil's team to read.

Trade-offs: a long rate-limit wait slows the run, and it gives up after 20 waits in a row.

Change if: rate limits get stricter; then slow the paging down.

**D-api-change - If VetOne changes its API, the run fails or warns; it never loads quietly wrong data.**

Status: Accepted, 9 Nov.

Context (why): VetOne is a live third-party system with incomplete docs, so its format can change without notice. Most changes already fail loudly (D-errors, D-test-severity, D-singular-tests), but three would have passed silently: a renamed `next_cursor` (only the first page would load), `include_deleted` no longer working (deleted appointments counted again), and `updated_since` changing meaning (late changes missed).

Decision (what):
- the `next_cursor` key must be on every page (VetOne sends `null` on the last one); if it's missing, the run stops
- a full page with no cursor logs a warning
- a missing `data` list or `access_token` stops the run with a plain message
- `Retry-After` is read as seconds or as a date
- a backfill with no deleted appointments logs a warning
- `dbt source freshness` warns if the newest change is more than 48 hours old
- the daily mart has a `last_loaded_at` column, so a stale view is visible

Each guard was tested with a fake response.

Rejected:
- **Failing on any new field:** APIs add fields all the time, and a new field can't make the numbers wrong.
- **Making freshness an error:** A long holiday weekend would block the morning report.
- **A weekly re-pull compared with raw:** The most thorough check, but a second code path to maintain (in Next steps).
- **A JSON schema / contract library:** More to explain than the handful of checks it replaces.

Consequences:

Trade-offs: about 40 lines of checks in the client; the 48-hour threshold is a guess from normal working days.

Change if: VetOne publishes a versioned API (then pin the version and drop some checks), or the warnings fire on normal days (then tune the threshold).

**D-atomic - Each pull is loaded all-or-nothing, in one transaction.**

All pages are collected first, then inserted in one transaction, so a crash mid-pull leaves raw exactly as it was.

Why: the backfill comes back sorted by `scheduled_at`, not `updated_at`. If half a backfill were saved, the next run would take its starting point from that half and silently skip the appointments it never fetched.

Rejected:
- **Saving page by page and resuming:** Needs a separate progress record; more to explain and maintain.

Trade-offs: the whole pull is held in memory, and the first backfill takes about 47 seconds to insert with a plain `executemany`; daily runs take under a second.

Change if: backfills grow too large for memory, or the insert time starts to matter.

**D-metadata - Every raw row gets `_loaded_at` and `_run_id`.**

Shows which run loaded which rows, and helps trace a bad load.

Rejected:
- **No metadata:** Simpler, but rows can't be traced back to a run.

Trade-offs: two extra columns on every raw row.

Change if: nothing foreseeable.

**D-clinics - Clinics are re-fetched every run and appended to `raw_clinics`, not overwritten.**

Evidence: API note [11](docs/vetone_api_notes.md#11-39-clinics-not-38-as-the-brief-says).

The raw layer is append-only for every table, so clinics follow the same rule as appointments. Each run adds one snapshot of 39 rows; staging takes the latest. It also keeps a record of when a clinic changed, e.g. went inactive.

Rejected:
- **Overwriting the clinics table each run:** Simpler to query, but breaks the append-only rule and loses when a clinic changed.

Trade-offs: 39 extra rows a day.

Change if: clinic history is never needed; then overwriting would do.

## dbt models

**D-materialization - Staging models are views; marts are tables.**

Staging is a thin cleanup over raw, so a view always shows the latest raw rows and stores nothing. Marts are what Power BI and Mette read, so they're built once per run as tables: fast to query, and a stable copy if a later run fails.

Rejected:
- **Everything as tables:** Duplicates raw in staging for no gain at this size.
- **Everything as views:** Power BI would re-run the whole chain on every refresh.
- **Incremental models:** Not needed at about 50,000 rows; a full rebuild takes under a second.

Trade-offs: marts are only as fresh as the last build.

Change if: the data grows a lot; then use incremental models.

**D-stg-clinics - `stg_vetone__clinics` takes the newest snapshot by `_run_id`.**

`_run_id` is the run's UTC start time, so the highest one is the latest load. Inactive clinics stay in staging; the marts decide whether to show them.

Rejected:
- **The latest row per clinic id across all snapshots:** Would keep a clinic that VetOne has removed entirely.

Trade-offs: relies on `_run_id` sorting in time order.

Change if: the run id format changes.

**D-dedupe - `stg_vetone__appointments` keeps the latest version per id, then drops deleted.**

Evidence: API notes [1](docs/vetone_api_notes.md#1-deleted-appointments-are-hidden-by-default), [4](docs/vetone_api_notes.md#4-updated_since-includes-the-boundary-and-updated_at-is-mostly-whole-minutes).

`qualify row_number() over (partition by id order by updated_at desc, _loaded_at desc) = 1`, with `_loaded_at` breaking ties when the same version was fetched twice. The dedupe happens *before* the deleted filter: if an appointment is deleted after we loaded it, its newest version is the deleted one, so it disappears. Checked against the same logic recomputed in plain Python: identical.

Rejected:
- **Deduping in Python before loading:** Raw would lose the history of status changes.
- **Filtering deleted rows before deduping:** Would bring deleted appointments back from their older versions.
- **`select distinct`:** Keeps every version whose status differs.

Trade-offs: `qualify` isn't T-SQL, so the dedupe needs rewriting for Azure.

Change if: moving to Azure SQL.

**D-timestamps - Cast to `timestamptz` with the dbt session in UTC; take the local date from the text.**

Evidence: API note [12](docs/vetone_api_notes.md#12-response-shape-and-timestamp-formats).

- All timestamps are cast to `timestamptz`, never `timestamp`, which silently drops the offset: `cast('2026-11-09T13:28:00+01:00' as timestamp)` gives 13:28, not 12:28 UTC. `profiles.yml` sets the session timezone to UTC.
- `scheduled_date_local` is the first 10 characters of `scheduled_at`. VetOne already sends the clinic's local time, so its date part *is* the clinic's day, and "a day" runs midnight to midnight in each clinic's own time.
- `scheduled_at_local` is the local wall-clock time (e.g. 08:00), for time-of-day views.

Rejected:
- **Converting UTC back through each clinic's timezone:** Needs a join to clinics and gives the same answer, since VetOne already sends local time.

Trade-offs: relies on VetOne always sending local time with an offset.

Change if: Mette wants one company-wide cut-off time instead.

**D-test-severity - Unknown `service` values warn; unknown `status` values fail the run.**

Evidence: API note [17](docs/vetone_api_notes.md#17-data-quality-is-clean).

Status drives the no-show metric, so an unexpected status must stop the run before Mette sees wrong numbers. A new service type doesn't change the metric, so it should be noticed without blocking the morning report.

Rejected:
- **Failing on both:** A harmless new service would block the report.
- **No service test:** A new service would go unnoticed.

Trade-offs: a new status stops the morning report until someone acts.

Change if: Nordvet prefers a report with a warning over no report.

**D-marts - Two mart tables, at two grains.**

- `mart_clinic_daily_noshows`: one row per clinic per local day. Mette's morning view and Power BI trends both come from it.
- `mart_clinic_noshow_ranking`: one row per active clinic, built *from the daily mart*, so the as-of date and the settled rule are defined once.

The SQL uses `sum(case when …)` rather than DuckDB-only functions, so the marts move to Azure SQL with few changes.

Rejected:
- **A separate "yesterday" table:** A filter on the daily mart does it, with one less model to keep in step.
- **One wide table with both grains:** Mixes daily rows and clinic totals; easy to double-count.
- **Doing the ranking in Power BI only:** The logic would live outside SQL, untested.

Trade-offs: two tables to keep in step.

Change if: Power BI needs a different grain, e.g. per vet.

**D-as-of - "Today" is a dbt variable, defaulting to today's date in Copenhagen.**

`as_of_date` defaults to today in Copenhagen time; `dbt build --vars "{as_of_date: '2026-11-06'}"` rebuilds the marts as of any past morning. Used to reproduce FINDINGS.md numbers, to demo, and to re-run a past day.

Rejected:
- **Plain `current_date`:** It's the UTC date in our session, a day behind Copenhagen just after midnight.

Trade-offs: one more setting to understand.

Change if: nothing foreseeable.

**D-singular-tests - Three SQL test files in `nordvet_dbt/tests/`.**

- `assert_noshow_rates_between_0_and_1`: every rate in both marts is between 0 and 1
- `assert_noshow_rate_bounds_ordered`: lower ≤ confirmed ≤ upper on every clinic-day
- `assert_daily_mart_reconciles_to_staging`: each day's total in the mart equals the staging count, so nothing is lost or double-counted between layers

Each returns the offending rows, so a failure shows exactly what's wrong.

Rejected:
- **The `dbt_utils` package:** A dependency for two or three checks; plain SQL is easier for Emil's team to read.

Trade-offs: three custom SQL files to maintain.

Change if: many more checks are needed; then consider `dbt_utils`.


**D-dbt-run - `run_pipeline.py` runs `dbt build` as a subprocess after ingestion.**

`dbt build` runs every model and test in dependency order, so one command builds and checks the data, and it's the same command Emil's team would type. It runs only after ingestion has closed its DuckDB connection (one writer at a time), and uses the dbt installed next to the running Python. `dbt source freshness` runs first and only warns (D-api-change). If dbt fails, the run exits with code 1; raw stays loaded, so a plain re-run finishes the job.

Rejected:
- **dbt's Python API (`dbtRunner`):** Less familiar to a SQL team than the command line.
- **`dbt run` then `dbt test` separately:** A bad staging model would feed the marts before the tests run.
- **Separate manual steps:** Easy to run out of order (D-entry).

Trade-offs: dbt's output is mixed into the pipeline log.

Change if: production logging needs one format.

## Metric

**D-formula - no-show rate = no_show / (completed + no_show).**

Cancelled appointments are excluded, because a cancelled slot isn't a no-show.

Why: a cancelled slot can usually be rebooked or freed, while a no-show is time that was held and lost. Including cancellations would mix two different behaviours and make the rate look better than it is.

Rejected:
- **`no_show / all appointments`:** Cancellations would dilute the rate.
- **Counting late cancellations as no-shows:** See D-late-cancellations.
- **Including `booked` in the denominator:** It's unresolved, so it goes in the bounds instead (D-metric).

Trade-offs: clinics that cancel a lot of appointments late may look better than they are.

Change if: Nordvet decides late cancellations count as no-shows.

**D-metric - Unresolved past `booked` rows.**

Yesterday is shown per clinic as confirmed no-shows plus a separate "awaiting status" count, with the rate as a lower and an upper bound:
- lower = no_show / (completed + no_show + awaiting): every awaiting appointment turns out completed
- upper = (no_show + awaiting) / (completed + no_show + awaiting): every awaiting one is a no-show

Why: no-shows are recorded late, so at 8am most of yesterday's are still `booked` (API notes 14-15). On 5 Nov at 8am the confirmed rate was 1.8%, against 8.9% if every unresolved booking were a no-show. A rate for yesterday alone would mislead; counts and a range don't. The ranking uses settled days only (D-settled).

Rejected:
- **Counting unresolved bookings as no-shows:** Overstates, since most turn out completed.
- **Ignoring them:** Understates, and hides the gap.
- **A range as the only view:** Too wide on a single day to tell clinics apart.

Trade-offs: an extra count and two extra rate columns to explain to Mette.

Change if: Mette would rather wait a few days for final numbers, or VetOne offers a faster way to record no-shows.

**D-settled - The last 3 days count as unsettled.**

They're left out of the clinic-ranking rate: a day is settled when `days_ago > 3`. The 3 is a dbt variable (`unsettled_days`).

Why: 92% of no-shows are recorded within 3 days and 96% within 4 (API notes [14](docs/vetone_api_notes.md#14-statuses-are-recorded-late-and-at-different-speeds), [15](docs/vetone_api_notes.md#15-past-appointments-stay-booked-until-their-status-is-recorded)). The lag varies a little by clinic (82.5% to 100% within 3 days, 93% or more everywhere within 4), but not enough to change the ranking.

Rejected:
- **1 or 2 days:** Only 40% or 81% of no-shows recorded.
- **7 days:** All recorded, but the ranking would lag a week for about 4 points more completeness.

Trade-offs: a few no-shows arrive later (the slowest took about 5 days), so the ranking slightly understates every clinic's rate.

Change if: more history shows the lag getting longer; then raise `unsettled_days` to 4.

**D-last-open-day - Mette's "yesterday" is the last day any clinic was open.**

Evidence: API note [18](docs/vetone_api_notes.md#18-calendar-facts).

Clinics are closed on Sundays, so on a Monday calendar yesterday is empty. `is_last_open_day` marks the most recent day with any appointments across the network: Saturday on a Monday, the previous day otherwise, and it skips public holidays without needing a holiday calendar.

Rejected:
- **Strict calendar yesterday:** Empty every Monday and after holidays.

Trade-offs: a clinic with a quiet day simply has no row that day.

Change if: clinics start opening on Sundays.

**D-ranking-window - Two windows: the recent 28 settled days (ranked), and all settled history.**

- **Recent:** the newest 28 settled days. The rank uses this, so it reflects what's happening now, and several hundred appointments per clinic give a stable rate.
- **History:** every settled day since 1 Sep, as a baseline, so a clinic's recent rate can be compared with its own normal.
- **Why exactly 28:** it's 4 whole weeks, so every weekday counts 4 times. That matters because Mondays have the highest rate (10.5%).

Both are dbt variables, and each window shows its counts next to the rate, plus the gap to the network rate.

Rejected:
- **Only the recent window:** No baseline.
- **Only history:** Reacts slowly to change.
- **30 days or a calendar month:** An uneven weekday mix.

Trade-offs: changes in the last 3 days don't show in the ranking yet.

Change if: Mette wants faster signals; then use a shorter window.

**D-inactive - Inactive clinics are left out of the ranking but keep their daily history.**

Evidence: API note [11](docs/vetone_api_notes.md#11-39-clinics-not-38-as-the-brief-says).

CL-420 Ystad stays in the daily mart with `is_active = false` (its September data is real) and is filtered out of the ranking. `is_active` comes from the latest clinic snapshot, so a clinic marked inactive tomorrow drops out of the ranking on the next run with no code change. A clinic removed from VetOne entirely fails the `relationships` test, so the run stops instead of silently dropping its appointments.

Rejected:
- **Dropping inactive clinics everywhere:** Loses real history.
- **Ranking them:** A closed clinic in Mette's list is noise.

Trade-offs: the flag shows a clinic's status today, not on the day.

Change if: clinics reopen, or partial activity matters.

**D-money - Money lost = booked vet minutes lost to no-shows (`duration_minutes`), not kroner.**

VetOne has no prices, so Karin's "where are we losing money" is measured in vet time: the booked minutes of every no-show. Turning it into kroner needs Nordvet's revenue per vet hour, a single multiplication once they give it to us.

Rejected:
- **Guessing a price per service:** Would present made-up kroner as fact.

Trade-offs: minutes aren't money; Karin has to apply a rate.

Change if: Nordvet gives a revenue per vet hour.

**D-late-cancellations - Late cancellations stay "cancelled" for now; flagged to discuss with Nordvet.**

Evidence: API note [16](docs/vetone_api_notes.md#16-a-fifth-of-cancellations-are-recorded-after-the-appointment-started).

About 1 in 5 cancellations is recorded *after* the appointment started, which suggests a patient who didn't come. Counting them as no-shows would raise no-shows by about 22%. The metric is fixed with Nordvet, so they stay cancellations in this slice, raised as a question for Mette.

Rejected for now:
- **Counting them as no-shows:** Changes the agreed metric without the client.
- **Adding a `late_cancellations` column now:** Better built once Nordvet has said what a late cancellation means.

Trade-offs: about 20% of cancellations may hide no-shows.

Change if: Mette decides they count as no-shows.

**D-fields - patient_ref and vet_id not stored; updated_at, cancelled_at, deleted_at and created_at kept.**

`patient_ref` and `vet_id` are dropped in Python before loading, so the pipeline never stores them. `created_at` is kept although nothing uses it yet, because it allows a later lead-time analysis.

Exception, outside the pipeline: the raw API responses saved during exploration (`data/explore/`) and the SQLite-era dumps in `data/` do contain both fields. They're local only, never committed, and should be deleted once their evidence isn't needed (Next steps).

Rejected:
- **Storing every field VetOne sends, including `patient_ref`:** Patient-related and not needed.
- **Storing `vet_id`:** Out of scope for a clinic view.

Trade-offs: a vet-level analysis would need a re-load from the API.

Change if: Nordvet wants vet-level reporting, e.g. to see whether Aarhus C's 24% comes from one vet's diary. Then add `vet_id` and re-run the backfill; `patient_ref` stays out unless there's a clear, agreed purpose.

## Findings

**D-findings - FINDINGS.md short list for Mette.**

Why: the brief asks for "a short list (or simple dashboard), no slides", and Mette needs answers to act on, not a tool to learn.

Rejected:
- **Slides:** The brief rules them out.
- **A Power BI report now:** More time than the slice allows, and it depends on Nordvet's licence.

Trade-offs: it's a snapshot (D-findings-snapshot), not a live view.

Change if: the Power BI report is built; it then becomes the morning view and FINDINGS.md a one-off analysis.

**D-findings-snapshot - FINDINGS.md is frozen at Mon 9 Nov 2026 (run 20261109T135405Z).**

The data is live, so numbers re-run later drift. The header states the as-of date and load time, and the appendix links the SQL behind every number. In the interview, a fresh live run shows "today" next to it.

Rejected:
- **Regenerating it on interview day:** Fresher, but the text would need checking again.

Trade-offs: the numbers in the document drift from the live data.

Change if: a recurring report replaces it.

**D-morning-sample - Morning view sample: the 5 clinics with the most no-shows, sorted by count.**

On a single day the numbers are too small to rank by rate: on Sat 7 Nov, 27 of 38 clinics had no no-shows, and the highest rates were 1 out of 3 appointments. Sorting by number of no-shows answers "who needs a call today?". The worst/best comparison by rate goes in the ranking, where 28 days give enough appointments.

Rejected:
- **The 3 worst and 3 best by rate on one day:** The rates are noise at that size.
- **All 38 clinics:** Too long for a summary.

Trade-offs: clinics with the highest rate on a single day aren't shown.

Change if: Mette asks for daily rates.

**D-fte - Lost vet hours are also shown as full-time vets, assuming a 37-hour week.**

525 hours in 4 weeks is 131 hours a week, about 3.5 full-time vets at 37 hours (the Danish standard; Sweden's 40 hours gives 3.3). Worded as "the equivalent of about 3.5 full-time vets' booked time", since it counts booked appointment time only.

Rejected:
- **Hours only:** Accurate, but less meaningful to Karin at a glance.

Trade-offs: depends on the assumed working week.

Change if: Nordvet gives actual vet contract hours.

**D-findings-staging - Service and weekday findings are queried outside the marts for now.**

Findings 4 (service) and 5 (weekday) come from dbt analyses (D-analyses) rather than a mart. They're the most actionable findings, so they're included even though no mart holds them yet.

Rejected:
- **Leaving them out:** Loses the clearest "what to do".
- **Building a mart now:** More work than two numbers justify in this slice.

Trade-offs: two numbers aren't built and tested every run.

Change if: those findings are needed regularly; then build the mart.

## Production (Azure)

**D-azure - Production target: Container Apps Job + Key Vault + Azure SQL Database + Power BI.**

Described in the README, not built.

- **Azure SQL Database:** Emil's team already knows SQL Server tools, Power BI connects natively, and the data is tiny. The dbt models move with the `dbt-sqlserver` adapter; a handful of DuckDB-specific bits need T-SQL equivalents (the README lists them), and the raw loader switches to Azure SQL.
- **Container Apps Job:** runs the unchanged `python run_pipeline.py` daily, within the free monthly grant.
- **Container image:** the job needs a small Dockerfile, built and stored by Azure Container Registry, so nobody at Nordvet installs Docker. "No Docker" in the README applies to the laptop only.
- **Key Vault:** holds the VetOne credentials, passed in as environment variables, so no code changes.

About $10-30 a month in total (D-pricing).

Rejected:
- **A DuckDB file on Azure storage, with marts exported as Parquet:** Cheapest, with no SQL rewrite, but Power BI reads files rather than a database, and it's less familiar to Emil's team.
- **Microsoft Fabric:** Only sensible if Nordvet already pays for Fabric capacity.
- **Azure Functions:** A timer trigger works, but running dbt inside Functions is awkward.
- **Azure Data Factory for the extract:** It can load the data without code, but it can't run dbt, so a second job would still be needed, and the API's quirks would have to be rebuilt in its settings. It's the right path if Nordvet would rather not maintain any Python.
- **A scheduled pipeline in Azure DevOps or GitHub Actions:** Simplest and often free, but it uses a build tool as a scheduler, with weaker monitoring; a fair stop-gap.

Trade-offs: needs a T-SQL rewrite, a Dockerfile and a small monthly cost.

Change if: Nordvet already has Fabric capacity or prefers another platform; or Nordvet would rather not maintain any Python, then move the extract to Data Factory and keep a small job for dbt.

**D-pricing - Azure costs are USD list prices, as an order-of-magnitude estimate, not a regional quote.**

Wwe don't know which Azure region Nordvet would use or which currency it's billed in, and prices differ by both. Researching the price of each service in each likely region wasn't worth the time.  Karin's test only needs the order of magnitude: even 10 times higher, about $10-30 a month is negligible next to about 560 lost vet hours a month.

Decision (what): use Microsoft's standard USD list prices (the default on its pricing pages, checked 9-10 Nov), labelled as a rough estimate, and get a real quote as part of "Deploy to Azure".

Rejected:
- **An exact quote for Sweden Central in DKK:** The likely region and currency for a real deployment (EU and Nordic data, most clinics in Denmark), but it depends on details we don't know yet, and it would take time for no difference to the conclusion.

Trade-offs: the figures are indicative; Nordvet's actual bill will differ.

Change if: Nordvet approves the deployment; then price it for Sweden Central (or North Europe as a fallback) in Nordvet's billing currency.


## Next steps / what I'd change with more time

Ordered by priority: a working, trustworthy morning view for Mette first, then questions for Nordvet, then engineering hardening, then further analysis.

### First: put it in front of Mette
1. **Deploy to Azure:** Container Apps Job, Azure SQL, Key Vault and Power BI; the README's "To build" list (D-azure)
2. **Check the Power BI licence** before promising Mette a subscription email; not verified yet
3. **Build the Power BI report** on the marts, showing "Data last updated" from `last_loaded_at` (D-api-change)
4. **Delete the local dumps** in `data/` once their evidence isn't needed; they contain `patient_ref` and `vet_id` (D-fields)

### Next: questions for Nordvet
5. **Agree what a late cancellation is** with Mette, and check whether late cancellations cluster in particular clinics (D-late-cancellations)
6. **Agree a revenue per vet hour** with Karin, so lost time can be shown in kroner (D-money)
7. **Ask about reminders:** do clinics already send them, and do Monday appointments get one? (FINDINGS.md finding 5)
8. **Find out what changed at Odense C** (FINDINGS.md finding 2)

### Then: make it robust to run
9. **Add pytest** for the API client: paging, token expiry (including what an expired token returns) and the API-change guards, run in GitHub Actions (D-tests, D-errors, D-api-change)
10. **Route pipeline warnings** to the same Azure Monitor alert as failures, at a lower severity (D-api-change)
11. **Add a weekly cross-check:** re-pull the last 14 days and compare with raw, to catch `updated_since` drifting (D-api-change)
12. **Build a service/weekday mart** so FINDINGS.md findings 4 and 5 are tested every run (D-findings-staging)
13. **Host the dbt docs** as a static site in Azure (D-docs)

### Later: deeper analysis and nice-to-haves
14. **Re-check the recording lag per clinic** as history grows; Jönköping is slowest today (D-settled)
15. **Alert on no-show rises** against each clinic's own baseline; it can only fire about 4 days late (D-settled)
16. **Compare August with September** to check the 1 Sep baseline isn't hiding a summer effect (D-backfill)
17. **Add a vet-level view** for outlier clinics, if Nordvet wants it (D-fields)
18. **Analyse booking lead time** with `created_at`: do far-ahead or last-minute bookings no-show more?
19. **Rebuild past mornings** from the version history in raw, or measure exactly when each status changed
20. **Test whether `from`/`to` use local or UTC dates** (API notes, "Not yet observed")
21. **Add jitter and pacing** to the retries (D-errors)
22. **Speed up the backfill insert** if the 47-second load ever matters (D-atomic)
23. **Add Mac and Linux setup commands** to the README
