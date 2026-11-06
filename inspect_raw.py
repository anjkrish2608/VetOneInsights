import json, pathlib
from collections import Counter
from datetime import datetime, timezone

appts = json.loads(pathlib.Path("data/appointments_all_raw.json").read_text(encoding="utf-8"))
now = datetime.now(timezone.utc)

def start(a):
    return datetime.fromisoformat(a["scheduled_at"])

booked = [a for a in appts if a["status"] == "booked"]
past_booked = [a for a in booked if start(a) < now]
print("booked:", len(booked), "| of which already in the past:", len(past_booked))

by_day = Counter((a["scheduled_at"][:10], a["status"]) for a in appts)
for day in sorted({d for d, _ in by_day}):
    print(day, {s: by_day[(day, s)] for s in ("completed", "booked", "cancelled", "no_show")})