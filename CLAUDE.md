# Nordvet no-show pipeline (Heyra case study)

Read this file and DECISIONS.md before doing anything. Decisions in DECISIONS.md
are mine; don't change them without asking me first.
DECISIONS_v1.md is the original SQLite-era log, kept as a historical record.
Never edit it.

## The client and the problem
- Nordvet: 38 vet clinics in Denmark and Sweden, all on one practice system (VetOne).
- Mette (Head of Operations): "I want to start every morning knowing how each clinic
  did yesterday" on no-shows. This is the deliverable.
- Karin (CEO): wants to know where money is lost; platform must not cost more than the no-shows.
- Anders (Head of Digital): asked for real-time. We are NOT doing real-time (see DECISIONS.md).
- Emil (IT): team of two, SQL + Power BI people. They run this after handover,
  so keep everything simple and SQL-first.
- Nordvet is on Microsoft 365 and Azure. Production target is described in the
  README only; nothing is built in the cloud.

## What the brief asks for
1. Repo with a short README: how to run it, assumptions, what was left out on purpose,
   where it would run for Nordvet. No credentials in the repo.
2. Findings for Mette: FINDINGS.md short list (or simple dashboard). No slides.
3. Pipeline must run live on my laptop in the interview, from a clean start.
- Budget: 4-5 hours total. A first slice, not a finished product. Prioritise.
- Where something is unclear: decide, and write it down in DECISIONS.md.

## The VetOne API (docs are incomplete on purpose)
- Base URL and credentials come from .env (VETONE_BASE_URL, VETONE_CLIENT_ID,
  VETONE_CLIENT_SECRET). Never print, log or commit them.
- POST /auth/token with JSON {client_id, client_secret} -> bearer token. Tokens expire.
- GET /v1/clinics -> all clinics.
- GET /v1/appointments -> last 7 days by default. Params: clinic_id, from, to
  (YYYY-MM-DD), updated_since (ISO 8601), limit, cursor. Paginate with next_cursor.
- Changelog mentions include_deleted, vet_id, patient_ref, updated_since timezone offsets.
- It's a live system: data keeps changing. First call can take ~20s (scales to zero).
- Expect undocumented behaviour. When you find a quirk, show me the evidence
  (the raw response) and explain it. I'll log it in DECISIONS.md myself.

## Stack (decided: dbt + DuckDB, don't change without asking)
- Python: API ingestion only (auth, pagination, append raw rows to DuckDB).
- DuckDB: local warehouse, single file (e.g. nordvet.duckdb), gitignored.
- dbt-duckdb: all transformations and tests. Layers: sources (raw) -> staging -> marts.
- Raw layer is append-only. Staging dedupes to the latest updated_at per appointment id.
- Daily batch, not real-time.
- This replaced an earlier SQLite + SQL views plan; earlier SQLite work stays on main.
- Fallback: if dbt blocks progress, use plain SQL views in DuckDB. Ask me first.

## Metric decisions (fixed)
- no-show rate = no_show / (completed + no_show). Cancelled excluded.
- The last 3 days count as unsettled and are excluded from the clinic ranking rate.
- Yesterday per clinic = confirmed no-shows + a separate "awaiting status" count
  (past appointments still in `booked`).
- Keep lower/upper bound of the rate as two columns.
- Not storing patient_ref or vet_id (dropped in Python before loading).
  Keep updated_at, cancelled_at, deleted_at and created_at (see D-fields, D-deleted).

## How to work with me
- I'm a data analyst learning data engineering. I must be able to defend every line
  in the interview, so explain choices and name the alternatives you rejected.
- Propose a plan before writing code. Wait for my OK. Small steps.
- No Docker, no orchestrator, no classes, no retry frameworks unless I ask.
  Plain functions and plain SQL.
- Commit after each working step with a clear message. Never commit .env, *.duckdb,
  *.db, data dumps, or the case brief PDF (it contains the client secret).
- Never run destructive git commands (force push, reset --hard) without asking.

## Approach: work like a senior data engineer
- Design for the client who runs it after handover (Emil's 2-person SQL team), not
  to impress. Simple, boring, well-documented beats clever.
- Every run must be safe to repeat (re-running doesn't create duplicates or break
  anything), and must be able to pick up only new or changed data (updated_since).
- Handle late-arriving and changing data explicitly (statuses change after the fact).
- Fail loudly with clear error messages; log what happened (rows fetched, rows loaded,
  time taken) using the logging module, not print.
- Data quality checks live in dbt tests, not ad-hoc scripts.
- Senior-level means knowing what to leave out: record every deliberate omission in
  the README "Left out on purpose" section.

## Code standards
- Python 3.11+, type hints on function signatures, short docstrings on public functions.
- Format and lint with ruff (`ruff format`, `ruff check`). No other Python tooling.
- Config from environment variables (.env via python-dotenv). Provide .env.example
  with placeholder values only.
- No hard-coded URLs, paths or credentials in code.
- Pin dependencies in requirements.txt.
- dbt conventions:
  - layers: staging (`stg_vetone__<entity>`) -> marts (`fct_`/`dim_` or a clear
    mart name, e.g. `mart_clinic_daily_noshows`)
  - sources declared in `_sources.yml`
  - every model has a description and column descriptions in a `_<layer>.yml` file
  - tests: unique + not_null on keys, accepted_values on status, relationships
    appointments -> clinics
  - lowercase SQL, CTEs over subqueries, one model per file, `ref()`/`source()` only
    (no hard-coded table names)

## Repo structure (target)
```
README.md            # for Nordvet / Heyra reviewers (see below)
DECISIONS.md         # decision log (mine)
FINDINGS.md          # findings for Mette
CLAUDE.md
.env.example
.gitignore
requirements.txt
run_pipeline.py      # single entry point: ingest, then dbt build
ingestion/
  vetone_client.py   # auth, token refresh, pagination
  load_raw.py        # append raw rows to DuckDB
nordvet_dbt/
  dbt_project.yml
  profiles.yml       # local DuckDB path only, no secrets
  models/staging/
  models/marts/
  tests/             # singular SQL tests (D-singular-tests)
data/                # DuckDB file lives here, gitignored
docs/images/         # README screenshots (D-images)
```
Don't add folders or files beyond this without asking.

## README requirements (from the brief; must cover all four)
1. How to run it: prerequisites, setup (venv, pip install, .env), one command to run,
   how to see the output.
2. Assumptions made: about the data, the API, the metric.
3. What was left out on purpose, and why.
4. Where it would run for Nordvet: Microsoft 365 + Azure target architecture,
   including rough cost and who operates it.
Also include: a one-paragraph overview written for the client, a simple text diagram
of the flow (API -> raw -> staging -> mart -> Power BI), the data model (models and
grain), and a pointer to DECISIONS.md and FINDINGS.md.
- Never include credentials. Write for a reader who has never seen the project.
- Draft the README; I will edit it into my own words. Keep it short (aim for 1-2 screens
  per section, not an essay).

## Git workflow
- All dbt + DuckDB work happens on the branch `dbt-duckdb`. Check you're on it
  (`git branch --show-current`) before making changes; stop and tell me if not.
- `main` holds the earlier SQLite plan. Don't commit to main, and don't merge into
  main unless I ask. The branch history is meant to show the pivot clearly.
- Small commits, one working step each, with messages that say what and why
  (e.g. "Add raw appointments ingestion with cursor pagination").
- Don't rewrite history (no rebase, squash or amend of pushed commits).