# Nordvet no-show pipeline

Nordvet runs 38 veterinary clinics across Denmark and Sweden. All clinics use the same practice management system, VetOne, for bookings and patient records. 

This pipeline pulls appointments from VetOne once a day and produces a per-clinic no-show view. It shows yesterday’s confirmed no-shows plus appointments still awaiting a status, and a clinic ranking based on settled days only.

This is a first slice: it runs on a laptop today, and the target set-up in Nordvet's Azure is described below.

## The problem

Mette (Head of Operations) wants to start each morning knowing how every clinic did on no-shows yesterday. 

Karin (CEO) wants to know where money is being lost.

Constraints that shaped it: 
- a two-person SQL/Power BI team will run it (Emil)
- it has to cost less than the no-shows do (Karin)
- it runs as a daily batch rather than real-time, because a morning view doesn’t need streaming (Anders)

### More detail 
  - What we found: [FINDINGS.md](FINDINGS.md)
  - Why it's built this way: [DECISIONS.md](DECISIONS.md) (decisions are referred to as D-… below)
  - What the VetOne API actually does: [docs/vetone_api_notes.md](docs/vetone_api_notes.md)

---

## Quickstart
### Prerequisites
- Windows
- git 
-  **Python 3.13**. dbt doesn't install on Python 3.15 yet (D-python)
- VetOne API credentials from Nordvet IT

If you don't have 3.13: `py install 3.13` with the Python install manager, or the installer from python.org.

### Setup 

One-time setup. Open PowerShell in the folder where you want the project folder to be created.

```bash
git clone https://github.com/anjkrish2608/VetOneInsights.git
```

```bash
cd VetOneInsights
```

```bash
py -3.13 -m venv .venv
```

```bash
.venv\Scripts\python -m pip install -r requirements.txt
```

```bash
copy .env.example .env
```

Then open `.env` and fill in:
- `VETONE_BASE_URL`
- `VETONE_CLIENT_ID` 
- `VETONE_CLIENT_SECRET`

`.env` is gitignored; never commit it.

### Run (one command, from the repo root)

```bash
.venv\Scripts\python run_pipeline.py
```

The first run takes about 2 minutes: it backfills about 50,000 appointments from 1 Sep 2026. Pauses of up to a minute are VetOne rate-limiting, not a hang. 

Later runs take a few seconds. A successful run ends with `Pipeline run … finished`; a failed one exits with `FAILED` and the reason.


### Results
The findings for Mette, with the numbers explained, are in [FINDINGS.md](FINDINGS.md).

The two report tables live in `data/nordvet.duckdb`: `mart_clinic_daily_noshows` and `mart_clinic_noshow_ranking`.

Mette's morning view (last open day, most no-shows first, D-morning-sample):

```bash
.venv\Scripts\dbt show --project-dir nordvet_dbt --profiles-dir nordvet_dbt --limit 50 --inline "select clinic_name, appointments, no_shows, awaiting_status, round(100 * no_show_rate, 1) as rate_pct from {{ ref('mart_clinic_daily_noshows') }} where is_last_open_day order by no_shows desc, awaiting_status desc"
```

The ranking (worst no-show rate first over the recent settled days, D-ranking-window):

```bash
.venv\Scripts\dbt show --project-dir nordvet_dbt --profiles-dir nordvet_dbt --limit 50 --inline "select rank_recent, clinic_name, round(100 * no_show_rate_recent, 1) as rate_pct, no_shows_recent, lost_vet_hours_recent from {{ ref('mart_clinic_noshow_ranking') }} order by rank_recent"
```

Where the most vet time is lost (for Karin: total hours, so busy clinics rank higher, D-money):

```bash
.venv\Scripts\dbt show --project-dir nordvet_dbt --profiles-dir nordvet_dbt --limit 50 --inline "select clinic_name, lost_vet_hours_recent, no_shows_recent, round(100 * no_show_rate_recent, 1) as rate_pct, rank_recent from {{ ref('mart_clinic_noshow_ranking') }} order by lost_vet_hours_recent desc"
```
Browse the models and the lineage graph (after a run has finished, since DuckDB allows one writer at a time):

  ```bash
  .venv\Scripts\dbt docs generate --project-dir nordvet_dbt --profiles-dir nordvet_dbt
  ```

  ```bash
  .venv\Scripts\dbt docs serve --project-dir nordvet_dbt --profiles-dir nordvet_dbt
  ```

This opens a page in your browser showing every model, column and test with its description, and the lineage from the raw tables to the marts. Stop it with Ctrl+C.

Re-run a past morning, rebuild the marts as of any date (as in FINDINGS.md):

  ```bash
  .venv\Scripts\dbt build --project-dir nordvet_dbt --profiles-dir nordvet_dbt --vars "{as_of_date: '2026-11-09'}"
  ```

---

## How it works
Python fetches appointments and clinics from VetOne; dbt turns them into two report tables which are summarised in FINDINGS.md.

```
VetOne API ─► Python ingestion ─► raw ─► dbt staging ─► dbt marts ─┬─► FINDINGS.md (today)
                                                                     └─► Power BI (planned, see Azure section)
```

Python only does the API part; everything after the raw tables is SQL in dbt.

Each run fetches what changed in VetOne, checks that VetOne's data is fresh (`dbt source freshness`, a warning only), then runs `dbt build`, which builds the models and runs all data tests. It's safe to re-run at any time: nothing is duplicated or lost.

### How it copes with late data
VetOne's data changes after the fact: statuses are updated later, and no-shows are recorded late (half within about a day, 92% within 3 days). The pipeline handles this in four ways:
- **Nothing is overwritten.** Raw is append-only: every version of an appointment that VetOne sends is kept (D3).
- **Each run fetches only what changed**, using the newest `updated_at` already loaded, so old appointments whose status changed late are picked up too (D-incremental).
- **Staging keeps the latest version** of each appointment and drops deleted ones (D-dedupe, D-deleted).
- **Recent days are treated as unsettled.** Yesterday shows confirmed no-shows plus an "awaiting status" count, and the ranking uses only days older than 3 days (D-metric, D-settled).

### Data model

| Layer | Model | One row per | What it does |
|---|---|---|---|
| raw | `raw_appointments` | appointment, per run that fetched it | Exactly what VetOne sent, append-only, plus `_run_id` and `_loaded_at`. `patient_ref` and `vet_id` are never stored. |
| raw | `raw_clinics` | clinic, per run | A full snapshot of the clinic list on every run. |
| staging | `stg_vetone__appointments` | appointment | The latest version of each appointment, with deleted ones removed and timestamps typed. |
| staging | `stg_vetone__clinics` | clinic | The latest snapshot (39 clinics, 38 active). |
| mart | `mart_clinic_daily_noshows` | clinic per day | Counts, confirmed rate with lower/upper bounds, awaiting status, lost vet minutes, and `last_loaded_at` (when data last arrived). Mette's view: `is_last_open_day`. |
| mart | `mart_clinic_noshow_ranking` | active clinic | Rate over the newest 28 settled days (ranked) and over all history (baseline), with the gap to the network rate. |

### Data quality
All checked by `dbt build` on every run; a failure stops the run before the marts are rebuilt, so Mette never sees numbers from bad data:
- **Keys:** every appointment and clinic id is unique and present
- **Allowed values:** an unknown status fails the run; an unknown service only warns (D-test-severity)
- **Relationships:** every appointment belongs to a known clinic
- **Sanity:** rates are between 0 and 1, and lower ≤ confirmed ≤ upper
- **Reconciliation:** each day's total in the report matches staging, so nothing is lost between layers
- **Freshness:** a warning if VetOne hasn't sent a change in 48 hours (D-api-change)

---

## Repo structure

- [README.md](README.md): this file
- [FINDINGS.md](FINDINGS.md): the findings for Mette
- [DECISIONS.md](DECISIONS.md): every design choice, what was rejected and why
- [CLAUDE.md](CLAUDE.md): working instructions for the AI assistant used to build it
- [run_pipeline.py](run_pipeline.py): the one command; ingests, then runs dbt
- [requirements.txt](requirements.txt): pinned Python packages
- [.env.example](.env.example): the settings to fill in, with placeholder values
- [ingestion/](ingestion/): Python for the API part only
  - [vetone_client.py](ingestion/vetone_client.py): login, paging, retries, input checks
  - [load_raw.py](ingestion/load_raw.py): appends each run's rows to the raw tables
- [nordvet_dbt/](nordvet_dbt/): the dbt project (all SQL)
  - [models/staging/](nordvet_dbt/models/staging/): cleans raw data, one row per appointment and clinic
  - [models/marts/](nordvet_dbt/models/marts/): the two report tables
  - [tests/](nordvet_dbt/tests/): the three SQL data tests
  - [analyses/](nordvet_dbt/analyses/): the SQL behind each number in FINDINGS.md
- [docs/](docs/)
  - [vetone_api_notes.md](docs/vetone_api_notes.md): what the VetOne API actually does
  - [history/DECISIONS_v1.md](docs/history/DECISIONS_v1.md): the earlier SQLite-era decision log
- `data/`: the local DuckDB file (gitignored, created on the first run)

## Assumptions

**The metric**:
- No-show rate = no-shows ÷ (completed + no-shows). Cancelled appointments are left out (D-formula).
- "Yesterday" = the last day any clinic was open, so Saturday on a Monday (D-last-open-day).
- No-shows are recorded late: half within about a day, 92% within 3 days (D-metric, D-settled).
- The last 3 days are unsettled and left out of the ranking (D-settled).
- Money is measured as booked vet minutes lost, because VetOne has no prices (D-money). 
- "Full-time vets" assumes a 37-hour week (D-fte).

**The data:**
- VetOne sends each appointment's start in the clinic's local time; that date is the "day" (D-timestamps).
- `duration_minutes` is the booked length, fixed per service.
- Clinics are closed on Sundays. 
- VetOne lists 39 clinics (the brief says 38); Ystad is inactive and left out of the ranking (D-inactive).
- A cancellation recorded after the appointment started is still treated as a cancellation, not a no-show. This is a question for Nordvet (D-late-cancellations).

**The API** (testing evidence in [docs/vetone_api_notes.md](docs/vetone_api_notes.md)):
- Deleted appointments are hidden unless `include_deleted=true` is sent, and only the exact value `true` works (D-deleted).
- `updated_since` returns every appointment changed since a time, including old ones whose status changed late. The pipeline uses the newest `updated_at` it already has (D-incremental).
- `limit` is silently capped at 500; some wrong parameters return 200 with wrong data, so the code checks its own inputs (D-backfill, D-validate).
- Tokens last 60 minutes; VetOne returns temporary 500s and rate limits (429) with `Retry-After`, and the pipeline handles each (D-errors).

---

## Left out on purpose

| Left out | Why |
|---|---|
| Real-time | Mette needs yesterday, each morning. No-shows arrive a day late anyway, so real-time would show wrong numbers faster and cost more (D-batch). |
| Building anything in Azure | The brief asks for a local first slice; the Azure set-up is described below. |
| A Power BI report | FINDINGS.md covers Mette's question in this slice; the marts are ready for Power BI. |
| Kroner | VetOne has no prices; lost time is in vet hours until Nordvet gives a rate per hour (D-money). |
| Counting late cancellations as no-shows | Changes the agreed metric; raised with Nordvet instead (D-late-cancellations). |
| Vet- and patient-level analysis | Not needed for a clinic view; `vet_id` and `patient_ref` aren't stored (D-fields). |
| Python unit tests (pytest) | Data checks in dbt come first; unit tests for the API client are a next step (D-tests). |
| A weekly cross-check of recent data against VetOne | The guards in D-api-change catch most API changes; a full re-pull comparison is a next step. |
| A mart for service and weekday | Those two findings are queried by hand in FINDINGS.md for now (D-findings-staging). |
| Alerting on spikes | A next step once Mette has used the daily view. |
| An orchestrator (Airflow, Dagster, Prefect) | One daily job; a scheduled `python run_pipeline.py` is enough (D-entry). |
| Docker for running locally | A venv with pinned packages gives a repeatable set-up without installing Docker Desktop on the demo laptop. Production in Azure adds a small Dockerfile to package it (D-azure). |
| Incremental dbt models | A full rebuild takes about a second at this size (D-materialization). |
| dbt v2 | dbt Core v1 has the adapter support and documentation Emil's team will need (D-dbt-v1). |
| Hosting the dbt docs | They run locally; a static site in Azure is a small next step. |

---

## Where this runs for Nordvet (Azure)

Nordvet already uses Microsoft 365 and Azure, so the pipeline moves to Azure with as little new technology as possible. The Python and dbt code stays the same apart from the database it writes to.

```
Container Registry (image) ──┐
Key Vault (credentials) ─────┤
                             ▼
Azure Container Apps Job ──► VetOne API
(daily: python run_pipeline.py)
             │
             ▼
Azure SQL Database (dbt: raw ─► staging ─► marts)
             │
             ▼
Power BI report ──► Mette (email or Teams), Karin
```

The job runs at 06:00 and Power BI refreshes at 07:00, so the view is ready when Mette starts work. If a run fails, Azure Monitor emails Emil's team.


### Components
- **Azure Container Apps Job** runs the same `python run_pipeline.py` command on a daily schedule. A failed run exits with code 1, so Azure marks it failed and Azure Monitor emails the team.
- **Azure Container Registry** holds the job's container image: Python 3.13, the pinned packages and this code, described in a small Dockerfile (about 8 lines). The registry builds the image in the cloud, so nobody at Nordvet needs Docker installed, and the code doesn't change.
- **Azure Key Vault** holds the VetOne credentials. They reach the job as environment variables, which the code already reads, so no code changes.
- **Azure SQL Database** replaces the DuckDB file (D3, D-azure). Emil's team already knows SQL Server tools, and Power BI connects to it natively. The dbt models move with the `dbt-sqlserver` adapter (only `profiles.yml` changes to point at Azure SQL), and the raw loader switches from DuckDB to an Azure SQL connection. DuckDB and SQL Server speak slightly different SQL, so these need T-SQL equivalents:
  - `qualify row_number() … = 1` in the dedupe → `row_number()` in a CTE, then `where rn = 1`
  - `timezone('Europe/Copenhagen', …)` for the as-of date → `at time zone 'Central European Standard Time'`
  - `strftime(date, '%Y-%m-%d')` in `clinic_day_id` → `format(date, 'yyyy-MM-dd')`
  - `datediff('day', a, b)` for `days_ago` → `datediff(day, a, b)`
  - `timestamptz` casts in staging → `datetimeoffset`
  - `boolean` columns and filters like `where is_settled` → `bit` and `where is_settled = 1`
  - `||` to join text in `clinic_day_id` → `concat()`
  - `dayname()` and `isodow()` in the weekday analysis → `datename(weekday, …)` and `datepart(weekday, …)`
- **Power BI** reads the two marts, refreshed after the job. Mette gets the morning view by email subscription or in Teams (e.g. via Power Automate), so there's nothing extra to open. To check with Nordvet first: subscription emails and sharing need Power BI Pro (or Premium Per User / capacity), so this depends on what their licence includes. Not verified yet.

### Rough monthly cost
Rough estimate in USD list prices (checked 9–10 Nov 2026); a real quote for Nordvet's region and currency comes with the deployment (D-pricing).

| Item | Cost |
|---|---|
| Container Apps Job | **$0**: a 2-minute daily run uses about 1% of the free monthly grant (180,000 vCPU-seconds) |
| Azure SQL Database, Basic (5 DTU, 2 GB) | **about $5** (up to about $20 in some regions); the data is tens of MB |
| Container Registry, Basic | **about $5** ($0.167 a day, 10 GB included; checked 10 Nov) |
| Key Vault, Azure Monitor | **a few dollars at most** |
| **Infrastructure total** | **about $10–30 a month** |
| Power BI Pro | $14 per user per month; included in Microsoft 365 E5, so Nordvet may already have it |

**Against Karin's test** 
"The platform must not cost more than the no-shows": the infrastructure is estimated at about $10–30 a month, while no-shows cost about 560 vet hours a month, so we are in the clear.

### Who runs it
- **Emil's team** owns it after handover. They change the SQL models (dbt is SQL plus a little YAML), watch the failure alert and re-run a failed day with the same command.
- **If VetOne changes its API**, the run either stops with a message naming what changed (a missing field or key, a new status, an error code) or logs a warning to look out for: `VetOne data looks stale`, `Last page was full …` or `Backfill has no deleted appointments`. It doesn't load quietly wrong numbers. After a failed run, Mette's view keeps the last good numbers, and `last_loaded_at` shows how old they are (D-api-change).
- **Nordvet IT** owns the VetOne credentials and rotates them in Key Vault.
- **Heyra** hands over the repo, this README, FINDINGS.md, DECISIONS.md and the VetOne API notes, and a walkthrough of the dbt docs.

---

## What we'd do next
1. **Deploy to Azure:** Container Apps Job, Key Vault and Azure SQL, as described above (D-azure).
2. **Power BI report** on the two marts for Mette, with "Data last updated" from `last_loaded_at`, after checking what Nordvet's Power BI licence includes.
3. **Agree late cancellations and a vet-hour rate with Mette and Karin:** is a cancellation recorded after the appointment started really a no-show (D-late-cancellations), and what is a vet hour worth, so lost time can be shown in kroner (D-money)?
4. **pytest for the API client:** paging, token expiry and the API-change guards, using recorded responses (D-tests, D-api-change).
5. **Service/weekday mart,** so those two findings are built and tested every run instead of queried by hand (D-findings-staging).

The full list, with the reasons, is in [DECISIONS.md → Next steps](DECISIONS.md#next-steps--what-id-change-with-more-time).