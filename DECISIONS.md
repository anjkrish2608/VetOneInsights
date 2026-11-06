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

## Metric and reporting rules
- **"Yesterday" defined per clinic, midnight to midnight in that clinic's own timezone.** 
  Why: the API provides a timezone for every clinic (Europe/Copenhagen for DK, Europe/Stockholm for SE). Both countries share the same clock time, but reading the field means I don't hardcode that assumption. Note timezone does not conflict with appointment time (summer not tested).
  Change if: Mette wants one company-wide cut-off time instead.
 
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