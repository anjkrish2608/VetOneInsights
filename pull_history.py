import json
import os
import pathlib
import time
from collections import Counter
from datetime import date

import requests
from dotenv import load_dotenv

load_dotenv()
base = os.environ["VETONE_BASE_URL"]

DATE_FROM = "2026-09-01"          # your decision: how far back to load
DATE_TO = date.today().isoformat()
MAX_PAGES = 400                   # safety stop so a bug can't hammer a live API
HISTORY_FILE = pathlib.Path("data/appointments_history_raw.json")


def get_token():
    r = requests.post(
        f"{base}/auth/token",
        json={"client_id": os.environ["VETONE_CLIENT_ID"],
              "client_secret": os.environ["VETONE_CLIENT_SECRET"]},
        timeout=60,  # first call can take ~20s: the API scales down when idle
    )
    r.raise_for_status()
    return r.json()["access_token"]


token = get_token()


def get_page(params):
    """401: new token, retry once. 429: wait as told. 5xx: retry with growing pauses.
    Other 4xx: return at once, since retrying can't fix a bad request."""
    global token
    refreshed = False
    for attempt in range(1, 7):
        r = requests.get(
            f"{base}/v1/appointments",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=60,
        )
        if r.status_code == 401 and not refreshed:
            print("  401: fetching a new token and retrying once")
            token = get_token()
            refreshed = True
            continue
        if r.status_code == 429:
            retry_after = r.headers.get("Retry-After")
            try:
                wait = int(retry_after)
            except (TypeError, ValueError):
                wait = 15  # header missing or not a number of seconds
            print(f"  429: Retry-After header = {retry_after!r}; waiting {wait}s")
            time.sleep(wait)
            continue
        if r.status_code < 500:
            return r
        print(f"  {r.status_code} on attempt {attempt}/6: {r.text[:150]}")
        time.sleep(2 ** attempt)
    return r


by_id = {}
if HISTORY_FILE.exists():
    for a in json.loads(HISTORY_FILE.read_text(encoding="utf-8")):
        by_id[a["id"]] = a
    # Resume from the last day already saved (re-fetching that day, de-duplicated by id)
    DATE_FROM = max(a["scheduled_at"][:10] for a in by_id.values())
    print(f"resuming: {len(by_id)} rows already saved, restarting from {DATE_FROM}")

params = {"from": DATE_FROM, "to": DATE_TO, "limit": 200}
pages = 0
stop_reason = None

while pages < MAX_PAGES:
    r = get_page(params)
    if r.status_code != 200:
        stop_reason = f"HTTP {r.status_code}: {r.text[:200]}"
        break
    page = r.json()
    rows_in_page = page["data"]
    for a in rows_in_page:
        by_id[a["id"]] = a
    pages += 1
    cursor = page.get("next_cursor")   # <- the line that was missing
    if pages <= 5 or pages % 20 == 0:
        first = rows_in_page[0]["scheduled_at"][:10] if rows_in_page else None
        last = rows_in_page[-1]["scheduled_at"][:10] if rows_in_page else None
        print(f"page {pages}: {len(rows_in_page)} rows | {first} to {last} "
              f"| cursor: {bool(cursor)} | total: {len(by_id)}")
    if pages % 20 == 0:
        # Save progress, so a crash or a stop loses at most 20 pages
        HISTORY_FILE.write_text(
            json.dumps(list(by_id.values()), ensure_ascii=False), encoding="utf-8"
        )
    if not cursor:
        stop_reason = "no next_cursor in the response (end of data)"
        break
    params = {"limit": 200, "cursor": cursor}  # the cursor carries the from/to filters
    time.sleep(0.5)  # be polite to the live system

if stop_reason is None:
    stop_reason = f"hit MAX_PAGES ({MAX_PAGES})"

all_appts = list(by_id.values())
pathlib.Path("data").mkdir(exist_ok=True)
HISTORY_FILE.write_text(json.dumps(all_appts, ensure_ascii=False), encoding="utf-8")

clinics = json.loads(pathlib.Path("data/clinics_raw.json").read_text(encoding="utf-8"))["data"]
country = {c["id"]: c["country"] for c in clinics}
ids = [a["id"] for a in all_appts]
dates = sorted(a["scheduled_at"][:10] for a in all_appts)

print("STOP REASON:", stop_reason)
print("pages this run:", pages, "| total rows:", len(all_appts))
print("asked for:", DATE_FROM, "to", DATE_TO)
print("got dates:", dates[0], "to", dates[-1], "|", len(set(dates)), "distinct days")
gap = (date.fromisoformat(DATE_TO) - date.fromisoformat(dates[-1])).days
if gap > 3:
    print(f"WARNING: latest appointment is {gap} days before {DATE_TO}. The pull looks INCOMPLETE; do not load it.")
print("duplicate ids:", len(ids) - len(set(ids)))
print("statuses:", Counter(a["status"] for a in all_appts))
print("offsets by country:",
      Counter((country.get(a["clinic_id"]), a["scheduled_at"][-6:]) for a in all_appts))
print("unknown clinic ids:", {a["clinic_id"] for a in all_appts} - set(country))
print("rows at inactive clinic CL-420:", sum(1 for a in all_appts if a["clinic_id"] == "CL-420"))