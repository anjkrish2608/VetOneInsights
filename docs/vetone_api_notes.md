# VetOne API notes

What the VetOne API and its data actually do, compared with what the docs say. These are
observations, not choices: the choices they led to are in [DECISIONS.md](../DECISIONS.md)
(the D-… references below).

Found mostly during the API exploration on 9 Nov 2026, some earlier in the SQLite-era work
([history/DECISIONS_v1.md](history/DECISIONS_v1.md)). Raw responses from the exploration are in
`data/explore/` (gitignored, so local only).

Each note has four parts:
- **Observed:** what the API or data does
- **Evidence:** the call or numbers that show it
- **Impact:** what it would break or distort if ignored
- **Handled:** what the pipeline does about it

Contents: [API behaviour](#api-behaviour) (1-13) · [Data behaviour](#data-behaviour) (14-18) ·
[Tooling](#tooling) (19-21) · [Not yet observed](#not-yet-observed)

---

## API behaviour

### 1. Deleted appointments are hidden by default
- **Observed:** without `include_deleted=true`, deleted appointments are simply left out.
  With it, they come back with a `deleted_at` field and a normal-looking status (e.g. `completed`).
  `deleted_at` is never after `updated_at`.
- **Evidence:** default 7-day pull: 5,442 rows. Same pull with the flag: 5,496, of which 53
  had `deleted_at`. In the first backfill, 702 appointments were deleted.
- **Impact:** raw is append-only, so an appointment loaded before it was deleted would stay
  in the counts forever.
- **Handled:** always send `include_deleted=true`; staging keeps the latest version per id,
  then drops deleted rows (D-deleted, D-dedupe).

### 2. `include_deleted` silently ignores values it doesn't recognise
- **Observed:** only `true` (or `True`) works. Other values return 200 OK and no deleted rows.
- **Evidence:** page 1 with `true`: 3 deleted rows; with `1` or `yes`: 0, no error.
- **Impact:** a harmless-looking change (`1` instead of `true`) would quietly bring back problem 1.
- **Handled:** the value is hard-coded as the string `"true"` in one place (D-validate).

### 3. `updated_since` drops the default 7-day window
- **Observed:** with `updated_since`, appointments of any date come back if they changed
  since that time, including future bookings.
- **Evidence:** `updated_since=2026-11-02T00:00:00Z` returned appointments scheduled from
  28 Oct (12 late no-shows, 6 late completions) to 9 Dec.
- **Impact:** good news: late status changes on older appointments can be fetched incrementally.
- **Handled:** the daily run uses `updated_since` = the newest `updated_at` already loaded
  (D-incremental).

### 4. `updated_since` includes the boundary, and `updated_at` is mostly whole minutes
- **Observed:** rows stamped exactly at the `updated_since` value come back again.
- **Evidence:** querying from `2026-11-08T07:31:00Z` returned both rows with that exact
  `updated_at`. 4,576 of 5,442 `updated_at` values end in `:00` seconds.
- **Impact:** each run re-fetches a few rows it already has. Starting one second later
  instead could miss rows written in the same minute.
- **Handled:** the overlap is kept on purpose; staging dedupes it (D-incremental, D-dedupe).

### 5. `updated_since` timezone handling
- **Observed:** any offset works, and a value without an offset is read as UTC. An
  unencoded `+` fails. A bare date is accepted as midnight UTC.
- **Evidence:** `...09:00:00Z`, `...10:00:00+01:00`, `...04:00:00-05:00` and `...09:00:00`
  all returned the same 398 rows. A raw `+01:00` in the URL: `400 {"error":"invalid updated_since"}`.
- **Impact:** a hand-built URL with `+` would fail. A value without an offset would be read as UTC,
  so a local-time value would silently shift by an hour or two.
- **Handled:** the watermark is always sent in UTC with `Z`, through `requests`, which encodes it;
  values without a timezone are rejected before calling (D-validate).

### 6. Leaving out `from` or `to` changes the window a lot
- **Observed:** no parameters: 7 days back to today. `from` only: open-ended into future
  bookings. `to` only: all history. `from` after `to`: 200 OK with 0 rows. Both dates are
  inclusive; a datetime instead of a date gets a 400.
- **Evidence:** `from=to=2026-11-05` gave 850 rows, all on 5 Nov. `to=2026-11-03` alone
  pulled 60,000 rows back to 31 Jul before a safety cap stopped it.
- **Impact:** an empty day reported as success, or a daily run turning into a full-history pull.
- **Handled:** `from` and `to` are always sent together and checked before calling (D-backfill,
  D-validate).

### 7. `limit` is silently capped at 500
- **Observed:** any value above 500 returns 500 rows; the default is 100.
- **Evidence:** `limit=1000` and `limit=5000` both returned 500 rows. `0`, `-1` and `abc` get
  `400 invalid limit`.
- **Impact:** code saying 1,000 would mislead readers; the default would mean 5x more calls on
  a rate-limited API.
- **Handled:** `limit=500` (D-backfill).

### 8. The cursor carries its own filters
- **Observed:** `next_cursor` is signed base64 JSON holding the original filters, an as-of
  timestamp and a sort key (`scheduled_at`, `id`). Filters sent alongside a cursor are ignored.
- **Evidence:** a cursor from a `clinic_id=CL-220` query, sent with `clinic_id=CL-941`, still
  returned CL-220 rows. An edited cursor: `400 invalid cursor`. Reusing a cursor returns the same
  page. No duplicate ids within any full pull (up to 14,238 rows).
- **Impact:** paging is stable; changing filters mid-pull has no effect.
- **Handled:** after page 1 only the cursor is sent (`vetone_client.fetch_appointments`).

### 9. Tokens last 60 minutes, but the token response doesn't say so
- **Observed:** the token response has only `access_token` and `token_type`. The expiry is
  inside the token itself.
- **Evidence:** the token's first part decodes to `{typ, cid, exp}`; `exp` minus issue time is
  exactly 60.0 minutes. A bad token gets `401 invalid token`; no token gets `401 missing bearer token`.
- **Impact:** only the first backfill could cross the hour.
- **Handled:** fresh token at the start of each run; on a 401, one new token and one retry (D-errors).

### 10. Transient errors and rate limits
- **Observed:** random `500 {"error":"temporary error, please retry"}`, and `429` with a
  `Retry-After` header when paging fast.
- **Evidence:** about 1 in 15 calls got a 500 on 9 Nov, all fine on retry. `Retry-After` values
  seen: 1-12s in exploration, 49-52s during backfills; 20, 19, 2 and 1s in the SQLite-era history pull.
- **Impact:** without retries, almost every backfill would fail.
- **Handled:** wait exactly `Retry-After` on a 429 (up to 20 times); 2/4/8/16s backoff on a 500
  or network error; never retry other 4xx (D-errors).

### 11. 39 clinics, not 38 as the brief says
- **Observed:** `/v1/clinics` returns 39 clinics in one page: 38 active, plus CL-420 Nordvet
  Ystad (SE), marked `active: false`. 24 in DK, 15 in SE. 7 fields: `id`, `name`, `city`,
  `country`, `timezone` (Europe/Copenhagen or Europe/Stockholm), `active`, `opened_on`.
- **Evidence:** no `next_cursor`, no duplicate ids. Ystad has appointments until September and
  none since.
- **Impact:** a closed clinic would sit at the bottom of Mette's ranking as noise.
- **Handled:** Ystad keeps its history in the daily mart but is left out of the ranking; asked
  in FINDINGS.md whether it's closed (D-inactive, D-clinics).

### 12. Response shape and timestamp formats
- **Observed:** records sit under a `data` key with `next_cursor` next to it. `scheduled_at` is
  the clinic's local time with an offset and no seconds (`2026-11-05T08:00+01:00`);
  `created_at`, `updated_at`, `cancelled_at` and `deleted_at` are UTC with `Z`.
- **Evidence:** every UTC field in raw (50,000+ rows) ends in `Z`.
- **Impact:** two time formats in one record; comparing them needs a proper timezone-aware type.
- **Handled:** staging casts all to `timestamptz` and takes the local date from `scheduled_at`'s
  text (D-timestamps; see also note 19).

### 13. The first call is slow
- **Observed:** the API scales to zero when idle, so the first call of a session can take about
  20 seconds.
- **Evidence:** stated in the brief; not caught in a timed call here. On 9 Nov the API was
  usually already awake (login 0.1-0.4s).
- **Impact:** a short request timeout would fail the run on a cold start.
- **Handled:** 60-second timeout per request; a timeout is retried like a 500 (D-errors).

---

## Data behaviour

### 14. Statuses are recorded late, and at different speeds
- **Observed:** completions are recorded within hours of the appointment; no-shows about a day
  later; cancellations mostly before the appointment.
- **Evidence:** time from `scheduled_at` to `updated_at` (re-measured 9 Nov on Sep-Oct
  appointments; the SQLite-era 7-day measurement is in brackets):

  | Status | Median | 90% within | Max |
  |---|---|---|---|
  | completed | 2.0h (2.0h) | 3.2h (3.2h) | |
  | no_show | 25.4h (25.2h) | 66.5h (53.6h) | 126.3h (117.2h) |
  | cancelled | 20.5h *before* start (20.8h) | 2.9h after (2.1h) | 5.0h after |

  No-shows recorded within 1 day: 40%; 2 days: 81%; 3 days: 92.3%; 4 days: 96.1%; 7 days: 100%.
  The SQLite-era window was only 7 days, so slow cases fell outside it and the lag looked shorter.
  Per clinic, the share within 3 days ranges from 82.5% (Jönköping) to 100%; within 4 days every
  clinic is at 93% or more.
- **Impact:** yesterday's no-show count is always incomplete at 8am, and recent days understate
  every clinic.
- **Handled:** confirmed no-shows plus "awaiting status", with lower/upper rates; the ranking uses
  only days older than 3 days (D-metric, D-settled).

### 15. Past appointments stay `booked` until their status is recorded
- **Observed:** the more recent the day, the more past appointments are still `booked`.
- **Evidence:** SQLite era (6 Nov): 241 past appointments still booked, by day 2-5 Nov: 3, 2, 20,
  56. 5 Nov at 8am: 13 no-shows and 56 still booked (1.8% confirmed vs 8.9% at most). No September
  day has any `booked` rows left; on 9 Nov only 3 appointments on settled days were still awaiting.
- **Impact:** a rate for yesterday alone would mislead.
- **Handled:** separate "awaiting status" count and rate bounds (D-metric); 3-day settled rule (D-settled).

### 16. A fifth of cancellations are recorded after the appointment started
- **Observed:** cancelling sets `updated_at` equal to `cancelled_at`, so late cancellations are
  picked up. But many are recorded after the start time, which suggests a patient who didn't come.
- **Evidence:** all 3,782 cancelled rows have `updated_at` = `cancelled_at`. 766 of 3,782 (20%)
  were cancelled after the start (median 2.8h, 90% within 4.6h, latest 5h); 743 of 3,519 (21%)
  in the settled window used in FINDINGS.md.
- **Impact:** counting them as no-shows would raise no-shows by about 22%.
- **Handled:** kept as cancellations (the agreed metric); raised as a question for Nordvet
  (D-late-cancellations).

### 17. Data quality is clean
- **Observed:** no structural problems in the data.
- **Evidence:** on 74,238 rows (Jul-Dec): no nulls in key fields; only the 4 known statuses
  (`booked`, `completed`, `cancelled`, `no_show`); no unknown clinic ids; `cancelled_at` set
  exactly when the status is cancelled; `updated_at` never before `created_at`; duration fixed per
  service (consultation 20 min, vaccination and follow-up 15, dental 45, surgery 90).
- **Impact:** none today; the risk is that it changes.
- **Handled:** dbt tests check it every run: unique and not-null keys, allowed statuses (fail) and
  services (warn), appointments -> clinics (D-tests, D-test-severity).

### 18. Calendar facts
- **Observed:** history starts on 31 Jul 2026. Clinics are closed on Sundays. Appointments run
  08:00-17:15 local. Offsets switch correctly at the 25 Oct clock change (+02:00 -> +01:00).
  Bookings reach about 30 days ahead.
- **Evidence:** `to`-only pull back to 31 Jul; no Sunday rows; `scheduled_at` hours and offsets by month.
- **Impact:** "yesterday" is empty every Monday; a backfill ending today would miss existing
  future bookings.
- **Handled:** "yesterday" = last open day (D-last-open-day); backfill from 1 Sep to 90 days
  ahead (D-backfill).

---

## Tooling

### 19. DuckDB `cast(... as timestamp)` silently drops the UTC offset
- **Observed:** casting a text timestamp with an offset to `timestamp` keeps the clock time and
  throws the offset away.
- **Evidence:** `cast('2026-11-09T13:28:00+01:00' as timestamp)` gives 13:28, not 12:28 UTC.
  `timestamptz`, with the session timezone set to UTC, gives 12:28.
- **Impact:** every `scheduled_at` would be off by one or two hours.
- **Handled:** staging uses `timestamptz` everywhere; `profiles.yml` sets the timezone to UTC
  (D-timestamps).

### 20. dbt-duckdb does not install on Python 3.15
- **Observed:** pip tries to compile `pyyaml` for 3.15 and fails without a C++ compiler.
- **Evidence:** `error: Microsoft Visual C++ 14.0 or greater is required` on 9 Nov.
- **Impact:** the pipeline can't run on the laptop's default Python.
- **Handled:** the project uses Python 3.13 (D-python).

### 21. Windows console and `dbt show` quirks
- **Observed:** printing DuckDB's table borders from Python in a Windows console that isn't UTF-8
  fails; `dbt show` adds its own `limit`, so an analysis that ends in `limit` fails.
- **Evidence:** `UnicodeEncodeError: 'charmap' codec can't encode characters`; `Parser Error:
  syntax error at or near "limit"`.
- **Impact:** the README's one-liner and one analysis broke on first try.
- **Handled:** the README uses `python -X utf8`; the top-5 analysis picks rows with
  `row_number()` instead of `limit` (D-analyses).

---

## Not yet observed

- **The response to an expired token.** The test token was deleted before it expired. The 401
  handling is tested with an invalid token instead (D-errors).
- **Whether `from`/`to` mean the clinic's local date or UTC.** Appointments run 08:00-17:15, so
  the two are always the same date and the data can't tell them apart (D-backfill, Next steps).
