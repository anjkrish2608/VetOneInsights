import json
import pathlib
import sqlite3
from datetime import datetime, timezone

DB_PATH = "data/nordvet.sqlite"

clinics = json.loads(pathlib.Path("data/clinics_raw.json").read_text(encoding="utf-8"))["data"]
appts = json.loads(pathlib.Path("data/appointments_all_raw.json").read_text(encoding="utf-8"))

pathlib.Path("data").mkdir(exist_ok=True)
conn = sqlite3.connect(DB_PATH)

conn.executescript("""
CREATE TABLE IF NOT EXISTS clinics (
    id        TEXT PRIMARY KEY,
    name      TEXT,
    city      TEXT,
    country   TEXT,
    timezone  TEXT,
    active    INTEGER
);
CREATE TABLE IF NOT EXISTS appointments (
    id               TEXT PRIMARY KEY,
    clinic_id        TEXT,
    service          TEXT,
    scheduled_at     TEXT,   -- kept as received: local time with offset
    duration_minutes INTEGER,
    status           TEXT,
    cancelled_at     TEXT,
    updated_at       TEXT,   -- UTC; used to detect changed rows
    loaded_at        TEXT    -- when this pipeline last wrote the row
);
""")

loaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

with conn:  # one transaction: all rows are written, or none
    conn.executemany(
        """INSERT INTO clinics (id, name, city, country, timezone, active)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
               name=excluded.name, city=excluded.city, country=excluded.country,
               timezone=excluded.timezone, active=excluded.active""",
        [(c["id"], c["name"], c["city"], c["country"], c["timezone"], int(c["active"]))
         for c in clinics],
    )
    conn.executemany(
        """INSERT INTO appointments
               (id, clinic_id, service, scheduled_at, duration_minutes,
                status, cancelled_at, updated_at, loaded_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
               clinic_id=excluded.clinic_id, service=excluded.service,
               scheduled_at=excluded.scheduled_at,
               duration_minutes=excluded.duration_minutes,
               status=excluded.status, cancelled_at=excluded.cancelled_at,
               updated_at=excluded.updated_at, loaded_at=excluded.loaded_at
           WHERE excluded.updated_at > appointments.updated_at""",
        [(a["id"], a["clinic_id"], a["service"], a["scheduled_at"],
          a["duration_minutes"], a["status"], a.get("cancelled_at"),
          a["updated_at"], loaded_at) for a in appts],
    )

# Check the load against what we saw in the raw data
print("clinics:", conn.execute("SELECT COUNT(*) FROM clinics").fetchone()[0], "(expect 39)")
print("appointments:", conn.execute("SELECT COUNT(*) FROM appointments").fetchone()[0], "(expect 5196)")
for status, n in conn.execute("SELECT status, COUNT(*) FROM appointments GROUP BY status ORDER BY 2 DESC"):
    print(" ", status, n)
conn.close()