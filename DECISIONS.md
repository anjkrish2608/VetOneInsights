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

**D-fields - patient_ref and vet_id not stored for now; updated_at and cancelled_at kept.**

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
Both dates are inclusive and are the clinic's local date.
Rejected:
- `limit=1000` or higher (works, but only because it is quietly capped; misleading to read)
- the default limit of 100 (5x more calls on a rate-limited API)
- open-ended `from` or `to` (unpredictable size; one test pulled 60,000 rows by accident)

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
- 429: wait exactly the `Retry-After` seconds, then retry. Seen values: 1-12 seconds.
- 500 ("temporary error, please retry"): retry up to 4 times with 2/4/8/16s pauses, then fail
  loudly and leave the previous data as it was. About 1 in 15 calls hit one on 9 Nov; all
  succeeded on retry.
- Other 4xx: never retry; the request itself is wrong, so fail at once with the message.
One small function with a loop, no retry framework.
Rejected:
- refreshing early by reading `exp` (relies on an undocumented token format)
- treating 429 like other 4xx and failing (broke the SQLite-era history pull)
- tenacity / urllib3 Retry (extra dependency, harder for Emil's team to read)

## API quirks found
(Log each one here: what you saw, the evidence, what you decided to do about it.)

## Next steps / what I'd change with more time
Candidates (Claude's suggestions: keep, edit or delete):
- Run it on a schedule in Azure (e.g. Container Apps job or Azure Function) instead of my laptop
- Move the models to Fabric Warehouse or Azure SQL (T-SQL has no QUALIFY, so the dedupe needs rewriting)
- Build a Power BI report on the final view for Mette
- Handle deleted appointments explicitly (include_deleted)
- Add alerting when a clinic's no-show rate spikes
- Add pytest for the API client (pagination, token expiry) and run checks in GitHub Actions