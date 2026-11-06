# Decisions

## Repo setup
- **using github as repo**

- **.gitignore: Python template#.**
  Why: the template already covers `.env` and virtual environments
  Rejected: Node and Terraform templates (not relevant to this project).
  Change if: XX
- **No license.**
  Why: it's a case submission, so a license adds nothing.
  Change if: the code were meant to be reused.
- **Public repo.**
  Why: the brief asks for a link that opens without an invite.
  Change if: they'd prefer a zip, in which case I'd send that instead.
- **created `.env` and `.env.example`.**
  Why: need to keep client id and client secret hidden but wanted to show example of what the pipeline requires
  Change if: the client secrets can be made public
- **.gitignore: Added `data/` and `.env` .**
  Why:  `data/` keeps API pulls and the database out of git, as the brief asks for no data dumps. `.env`need to keep client id and client secret hidden
  Change if: I needed to share a small sample file with reviewers, in which case I'd add an exception for it.

## Language
- **Python for extract and load.** (Under review)
  Why for now: I started with Python to get moving and haven't compared it properly yet.
  To decide: Python vs PowerShell vs Power Query vs Azure Data Factory, weighing what I can build and explain in the time, what Emil's team can maintain, and running cost.

- **decision made**
  Why: XX
  Change if: XX

## Data Observations
- **Token response has no expiry field**
  Documentation says tokens expire but toke  response has no expiry field.
  Planned Development: on a 401 will need to fetch a new token and retry once before further investigation
- **API responses are wrapped**
  records sit under a `data` key, not at the top level.
- **/v1/clinics returns 39 clinics (brief says 38)** 
  - 24 in DK
  - 15 in SE
  - 38 are active
  - 1 are marked inactive (Nordvet Ystad, SE)
  - No duplicate IDs
  - No paging requireed on this endpoint

- **/v1/appointments** 
  - paged, `limit = 200` amd `next_cursor`is returned
  - no price or cost field included -> can measure loss in billable minutes 
  - `scheduled_at` is local time with offset; `created_at`/- - - `updated_at` are UTC (`Z`).
  - default pulls last 7 days:
    - 5,196 appointments  
    - 26 pages
    - no duplicate IDs across pages
    - Statuses seen: 
      - completed 3,820
      - booked 701
      - cancelled 403
      - no_show 272
    - `cancelled_at` is filled only for cancelled appointments (403 rows).
    - Nordvet Ystad, SE has no active appointments in last 7 dayas as expcted 
    - One transient 500 on the page 4 request ("temporary error, please retry"); succeeded on the second attempt.
    - statuses are finalised at different speeds. Lags measured with `updated_at`; 7-day window only, so slow cases are censored.
        - Completed: median 2.0h after start (90th_p 3.2h.)
        - No-show: min 15.1h, median 25.2h, 90th_p 53.6h, max 117.2h.
        - Cancelled: median 20.8h before start, but 90th_p is 2.1h after start.
- 241 `booked` rows are in the past
   - 81 of them are from earlier days (2-5 Nov: 3, 2, 20, 56)
   - The more recent the day, the more are unresolved.
- Yesterday's no-show count is therefore incomplete at 8am: 5 Nov showed 13 no-shows and 56 still booked.

## Storage
- **SQLite as the store, with the business logic in SQL views.** 
  Why a database at all: 
  rows change after I first see them (no-shows are recorded a median 25 hours after the appointment), so I need to update rows by `id` instead of re-downloading a window.

  Why SQLite: 
  one file, nothing to install, runs on any laptop from a fresh clone. The views are plain SQL that Emil's team can read.

  Rejected: 
  - CSV files only (no keys, so no safe re-runs)
  - pandas in memory only (nothing persists, logic ends up in Python)
  - Parquet as the store (no in-place updates, so I'd be rebuilding a database badly)
  - DuckDB (extra tool to learn and explain, no clear gain at this size)
  - Postgres or SQL Server in Docker (setup risk on the demo laptop)
  - Azure SQL directly (needs a cloud account and costs money for a first slice).
  
  Limits: 
  single writer
  Power BI has no built-in SQLite connector
  date functions differ from SQL Server's (`strftime` vs `DATEPART`).

  For Nordvet: 
  Azure SQL with Power BI reading the same views. SQLite is the demo store.

## Extract and load
- **Retry server errors (5xx) up to 4 times with 2/4/8/16s pauses; never retry 4xx.** (Decided, built)
  Why: I saw a one-off 500 on page 4 ("temporary error, please retry") that succeeded on retry. A 4xx means my request is wrong, which retrying can't fix.
- **On a 401, fetch a new token and retry once.** (Planned, not built yet)
  Why: the token response has no expiry time. Once, because a second 401 means the problem isn't expiry, and repeated failed logins could trigger a lockout.
- **Load by upsert on appointment `id`, updating only when the incoming `updated_at` is newer, inside one transaction.** (Decided, to be verified by running the load twice)
  Rejected: delete and reload (simple, but loses what the pipeline has seen); append only (duplicates every changed row).
- **How far back to re-pull each run.** (Open)
  Options: a fixed window (14 days?) vs `updated_since` since the last successful run. Must test that `updated_since` really catches status changes before relying on it.
- **Fields loaded: id, clinic_id, service, scheduled_at, duration_minutes, status, cancelled_at, updated_at.** (Decided)
  Left out: `patient_ref` (patient-related and unneeded for a clinic view), `vet_id` (vet-level reporting is out of scope), `created_at` (unused).
  Change if: Nordvet wants vet-level reporting, in which case I'd add `vet_id` and re-load.


## Metric and reporting rules
- **"Yesterday" defined per clinic, midnight to midnight in that clinic's own timezone.** 
  Why: the API provides a timezone for every clinic (Europe/Copenhagen for DK, Europe/Stockholm for SE). Both countries share the same clock time, but reading the field means I don't hardcode that assumption. Note timezone does not conflict with appointment time (summer not tested).
  Change if: Mette wants one company-wide cut-off time instead.

- **how unresolved bookings are handled**
  Yesterday is shown as confirmed no-shows plus a separate "awaiting status" count. The clinic ranking uses a rate over settled days only. The SQL view also holds a lower and an upper rate.
  Why: no-shows are recorded slowly (median about 25h after the appointment, 90% within about 2.2 days), so yesterday's rate is always understated at 8am (5 Nov: 1.8% confirmed vs 8.9% if every unresolved booking became a no-show). A rate for yesterday alone would mislead Mette; counts she can read at a glance would not. Settled days give a stable ranking.
  Rejected: counting unresolved bookings as no-shows (overstates, since some will be completions); ignoring them (understates, and hides the gap); a range as the only view (too wide for yesterday to tell clinics apart).
  Change if: Mette would rather wait a few days for final numbers, or the API offers a faster way to mark no-shows.
NEED TO CONFIRM NUMBER IN SQL

- **Settled = appointments older than 3 days.** 
  The clinic ranking rate only uses those.
  Why: 90% of no-shows are recorded within about 2.2 days, so by day 3 most are in.
  Known limit: a few are recorded later (the slowest took nearly 5 days), so the ranking still slightly understates no-shows. That's acceptable because the bias applies to every clinic equally, though I haven't verified that.
  Change if: more history shows the lag is longer, in which case I'd raise the number.

- **No-show rate = no_show ÷ (completed + no_show); cancelled excluded.**
  Why: a cancelled slot can be rebooked; a no-show can't.
  Open question: is a very late cancellation a no-show? Check `cancelled_at` against `scheduled_at`.

- **Inactive clinics (CL-420 Ystad) excluded from Mette's view.** 
  Why: no appointments in the window, and no future slots to lose.

- **Money impact = lost vet-minutes from no-shows (`duration_minutes`), not kroner.** 
  Why: the API has no prices. Karin's "where are we losing money" can be mapped to lost billable vet minutes

## Pipeline choices
- **Retry server errors (5xx) up to 4 times with 2/4/8/16s pauses; never retry 4xx.**
  Why: the 500 was temporary and the response body said to retry, and a 4xx means my request is wrong, which retrying can't fix.
  Change if: errors persist, in which case I'd fail the run clearly and keep the previous data.

- **Load only the fields the metric or the pipeline uses. Left out: `patient_ref`, `vet_id`, `created_at`.**
  Why: `patient_ref` is patient-related and a clinic-level no-show view doesn't need it; `vet_id` and `created_at` aren't used by anything I'm building. `cancelled_at` is kept for the late-cancellation check; `updated_at` is kept so the pipeline can detect rows whose status changed.
  Change if: Nordvet wants vet-level reporting, in which case I'd add `vet_id` and re-load from the API.

- **Daily batch, not real-time.** 
  Why: Mette asked to know how yesterday went each morning, and no-show statuses arrive about a day late, so "real-time" would show wrong numbers faster. It's also cheaper, which matters for Karin.
  Rejected: real-time or streaming (Anders asked for it, but it adds cost and no usable accuracy).
  Change if: Nordvet adds a use case that acts within the hour, such as reassigning a vet when a patient doesn't arrive.

## Output for Mette
- **`FINDINGS.md`, a short list. No slides, no Power BI report.** 
  Why: the brief says "a simple dashboard or a short list". I focused on being confident in the metrics.
  Rejected: a Power BI report (stretch only, if time allows); an ODBC link from Power BI to SQLite (more setup, brittle).
  Optional later: export the final view as CSV or Parquet, which Power BI reads natively.

## Where it would run for Nordvet
- **Azure runs the pipeline and holds the data. Microsoft 365 is how Mette receives it.**
  Pipeline: a scheduled job (Azure Functions or a Container Apps Job) runs each morning, writes to Azure SQL, and keeps secrets in Key Vault.

  Reporting: Power BI reads the same SQL views. The report can be emailed each morning as a subscription, or posted to Mette in Teams or Outlook (for example through Power Automate), so she sees it without opening anything.

  Why: Nordvet's team already works in M365 and Power BI, so nothing new to learn or license beyond Azure. Emil's team can read and change SQL views.

  Rejected: running it on a laptop (nobody owns it); Data Factory for the extract (heavier than this needs, though a fair option if Nordvet wants no code); Fabric as the store (a real alternative, but more than a first slice needs. I'd compare cost before ruling it out).
  
  Check before the interview: what Nordvet's Power BI licence includes, since subscription emails and sharing depend on it. I haven't verified that.
  
## Open questions (assumption I made)
- **Set timeout to 60 in `explore.py`**
NEED TO ADD EXPLANATION

- **Inactive clinics**
Assumption: exclude them, since they have no future slots to lose. Check first whether Ystad has any recent appointments.

- **`patient_ref`and `vet_id`**
Assumption: not required for clinic level no show view. Best to not add unnecessary patient related data. Could be interesting to investigate these fields if a particular clinic is an outlier.

## Left out on purpose
- Real-time, alerting, vet-level and patient-level analysis, a Power BI report, tests beyond a clean-run check.

## If I had more time
- Test `updated_since` against a fixed window; build the 401 retry; check `include_deleted`; verify the lag is equal across clinics; add tests and a failed-run alert; move to Azure SQL and a scheduled job.