import json, pathlib
from collections import Counter
from datetime import datetime

appts = json.loads(pathlib.Path("data/appointments_all_raw.json").read_text(encoding="utf-8"))

def start(a):
    return datetime.fromisoformat(a["scheduled_at"])

def updated(a):
    return datetime.fromisoformat(a["updated_at"].replace("Z", "+00:00"))

# 1. How many hours after the scheduled start was each status last updated?
#    (negative = changed before the appointment, expected for cancellations)
for status in ("completed", "no_show", "cancelled"):
    lags = sorted((updated(a) - start(a)).total_seconds() / 3600 for a in appts if a["status"] == status)
    n = len(lags)
    print(status, "n =", n, "| hours after start, min/median/p90/max:",
          round(lags[0], 1), round(lags[n // 2], 1), round(lags[int(n * 0.9)], 1), round(lags[-1], 1))

# 2. Which clinics have unresolved past appointments (before today)?
today = datetime.now().date().isoformat()
stale = [a for a in appts if a["status"] == "booked" and a["scheduled_at"][:10] < today]
print("unresolved from earlier days:", len(stale))
print("by clinic:", Counter(a["clinic_id"] for a in stale).most_common(8))

# 3. Where did 2 Nov's no-show spike come from?
spike = [a for a in appts if a["status"] == "no_show" and a["scheduled_at"][:10] == "2026-11-02"]
print("2 Nov no-shows by clinic:", Counter(a["clinic_id"] for a in spike).most_common(8))