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
- **Python & SQL.**
  Why:
  Rejected: 
  Change if: 
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

## Pipeline choices
- **Retry server errors (5xx) up to 4 times with 2/4/8/16s pauses; never retry 4xx.**
  Why: the 500 was temporary and the response body said to retry, and a 4xx means my request is wrong, which retrying can't fix.
  Change if: errors persist, in which case I'd fail the run clearly and keep the previous data.
  
## Open questions (assumption I made)
- **Set timeout to 60 in `explore.py`**
NEED TO ADD EXPLANATION

- **Inactive clinics**
Assumption: exclude them, since they have no future slots to lose. Check first whether Ystad has any recent appointments.

- **`patient_ref`and `vet_id`**
Assumption: not required for clinic level no show view. Best to not add unnecessary patient related data. Could be interesting to investigate these fields if a particular clinic is an outlier.