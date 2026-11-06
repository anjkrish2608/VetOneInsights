import os
import requests
from dotenv import load_dotenv
import json
import pathlib
from collections import Counter

load_dotenv()
base = os.environ["VETONE_BASE_URL"]

# First call can take ~20s because the API scales down when idle
resp = requests.post(
    f"{base}/auth/token",
    json={
        "client_id": os.environ["VETONE_CLIENT_ID"],
        "client_secret": os.environ["VETONE_CLIENT_SECRET"],
    },
    timeout=60,
)

token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}


clinics = requests.get(f"{base}/v1/clinics", headers=headers, timeout=60)
print(clinics.status_code)
body = clinics.json()

# Save the raw response so I can explore offline without re-calling the API
pathlib.Path("data").mkdir(exist_ok=True)
pathlib.Path("data/clinics_raw.json").write_text(
    json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8"
)

rows = body["data"]
print("top-level keys:", list(body.keys()))
print("clinic count:", len(rows))
print("countries:", Counter(c["country"] for c in rows))
print("timezones:", Counter(c["timezone"] for c in rows))
print("active:", Counter(c["active"] for c in rows))
ids = [c["id"] for c in rows]
print("duplicate ids:", len(ids) - len(set(ids)))
print("all field names:", sorted({k for c in rows for k in c}))
print("inactive clinics:", [c for c in rows if not c["active"]])


import time

clinic_country = {c["id"]: c["country"] for c in rows}

def get_with_retry(url, params, headers, tries=4):
    """Retry server errors (5xx) with growing pauses; return 4xx at once, since retrying can't fix those."""
    for attempt in range(1, tries + 1):
        r = requests.get(url, headers=headers, params=params, timeout=60)
        if r.status_code < 500:
            return r
        print(f"  {r.status_code} on attempt {attempt}/{tries}: {r.text[:200]}")
        time.sleep(2 ** attempt)  # 2s, 4s, 8s, 16s: gentle on a live system
    return r

all_appts = []
params = {"limit": 200}
pages = 0
MAX_PAGES = 100  # safety stop so a bug can't hammer a live API

while pages < MAX_PAGES:
    r = get_with_retry(f"{base}/v1/appointments", params, headers)
    if r.status_code != 200:
        print(f"STOPPED on page {pages + 1}: {r.status_code} {r.text[:300]}")
        break
    page = r.json()
    all_appts.extend(page["data"])
    pages += 1
    print(f"page {pages}: {len(page['data'])} rows")
    cursor = page.get("next_cursor")
    if not cursor:
        break
    params = {"limit": 200, "cursor": cursor}
    time.sleep(0.2)  # be polite to the live system

pathlib.Path("data/appointments_all_raw.json").write_text(
    json.dumps(all_appts, ensure_ascii=False), encoding="utf-8"
)


print("pages:", pages, "| rows:", len(all_appts), "| hit safety cap:", bool(cursor))
ids = [a["id"] for a in all_appts]
print("duplicate ids across pages:", len(ids) - len(set(ids)))
times = sorted(a["scheduled_at"] for a in all_appts)
print("scheduled_at range (rough):", times[0], "to", times[-1])
print("statuses:", Counter(a["status"] for a in all_appts))
fields = sorted({k for a in all_appts for k in a})
print("rows with null/missing value, per field:",
      {f: sum(1 for a in all_appts if a.get(f) is None) for f in fields})
print("offsets by country:",
      Counter((clinic_country.get(a["clinic_id"]), a["scheduled_at"][-6:]) for a in all_appts))
print("unknown clinic ids:", {a["clinic_id"] for a in all_appts} - set(clinic_country))
print("rows at inactive clinic CL-420:", sum(1 for a in all_appts if a["clinic_id"] == "CL-420"))