import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()
base = os.environ["VETONE_BASE_URL"]

tok = requests.post(
    f"{base}/auth/token",
    json={"client_id": os.environ["VETONE_CLIENT_ID"],
          "client_secret": os.environ["VETONE_CLIENT_SECRET"]},
    timeout=60,
)
headers = {"Authorization": f"Bearer {tok.json()['access_token']}"}

# One page per window: enough to see whether data exists, without a full pull
windows = [
    ("2026-10-23", "2026-10-29"),
    ("2026-10-01", "2026-10-07"),
    ("2026-08-01", "2026-08-07"),
    ("2026-01-01", "2026-01-07"),
    ("2025-01-01", "2025-01-07"),
]

for date_from, date_to in windows:
    for attempt in range(1, 5):
        r = requests.get(
            f"{base}/v1/appointments",
            headers=headers,
            params={"from": date_from, "to": date_to, "limit": 200},
            timeout=60,
        )
        if r.status_code < 500:
            break
        print(f"  {r.status_code} on attempt {attempt}, retrying")
        time.sleep(2 ** attempt)
    if r.status_code != 200:
        print(date_from, date_to, "->", r.status_code, r.text[:200])
        continue
    body = r.json()
    rows = body["data"]
    dates = sorted(a["scheduled_at"][:10] for a in rows)
    print(date_from, "to", date_to, "->", len(rows), "rows",
          "| range:", (dates[0], dates[-1]) if dates else None,
          "| more pages:", bool(body.get("next_cursor")))
    time.sleep(0.3)  # be polite to the live system