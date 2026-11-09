"""Append raw VetOne rows to DuckDB.

Raw tables are append-only and hold values as the API sent them (timestamps as
text); dbt staging casts and dedupes. Each run's rows go in one transaction
(D-atomic). Personal fields are dropped here, before anything reaches disk (D-fields).
"""

import logging
import pathlib
import time
from datetime import datetime

import duckdb

log = logging.getLogger(__name__)

# Columns kept from the API, in table order. patient_ref and vet_id are left out on purpose.
APPOINTMENT_COLUMNS = [
    "id",
    "clinic_id",
    "service",
    "scheduled_at",
    "duration_minutes",
    "status",
    "created_at",
    "updated_at",
    "cancelled_at",
    "deleted_at",
]
APPOINTMENT_OPTIONAL = {"cancelled_at", "deleted_at"}  # only present on some rows
APPOINTMENT_DROPPED = {"patient_ref", "vet_id"}

CLINIC_COLUMNS = ["id", "name", "city", "country", "timezone", "active", "opened_on"]

CREATE_TABLES = """
create table if not exists raw_appointments (
    id                varchar not null,
    clinic_id         varchar not null,
    service           varchar,
    scheduled_at      varchar not null,  -- local time with offset, e.g. 2026-11-05T08:00+01:00
    duration_minutes  integer,
    status            varchar not null,
    created_at        varchar,           -- UTC, e.g. 2026-10-29T12:27:41Z
    updated_at        varchar not null,  -- UTC; drives the incremental watermark
    cancelled_at      varchar,
    deleted_at        varchar,
    _run_id           varchar not null,
    _loaded_at        timestamp not null -- UTC
);

create table if not exists raw_clinics (
    id          varchar not null,
    name        varchar,
    city        varchar,
    country     varchar,
    timezone    varchar,
    active      boolean,
    opened_on   varchar,
    _run_id     varchar not null,
    _loaded_at  timestamp not null
);
"""


def connect(db_path: str) -> duckdb.DuckDBPyConnection:
    """Open (or create) the DuckDB file and make sure the raw tables exist."""
    pathlib.Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(db_path)
    con.execute("set timezone = 'UTC'")
    con.execute(CREATE_TABLES)
    return con


def get_watermark(con: duckdb.DuckDBPyConnection) -> str | None:
    """Return the newest updated_at already loaded (ISO 8601, UTC), or None if raw is empty."""
    return con.execute(
        "select strftime(max(cast(updated_at as timestamptz)), '%Y-%m-%dT%H:%M:%SZ')"
        " from raw_appointments"
    ).fetchone()[0]


def _to_tuples(
    rows: list[dict], columns: list[str], optional: set[str], what: str
) -> list[tuple]:
    """Pick the kept columns from each row; fail loudly if a required field is missing."""
    out = []
    for row in rows:
        missing = [c for c in columns if c not in row and c not in optional]
        if missing:
            raise ValueError(f"{what} {row.get('id')!r} is missing fields {missing}")
        out.append(tuple(row.get(c) for c in columns))
    return out


def _warn_on_new_fields(rows: list[dict], known: set[str], what: str) -> None:
    """Log fields the API sends that we neither keep nor drop on purpose."""
    new = {k for row in rows for k in row} - known
    if new:
        log.warning("VetOne sent new %s fields, not loaded: %s", what, sorted(new))


def load_run(
    con: duckdb.DuckDBPyConnection,
    appointments: list[dict],
    clinics: list[dict],
    run_id: str,
    loaded_at: datetime,
) -> None:
    """Append one run's appointments and clinics in a single transaction."""
    _warn_on_new_fields(
        appointments, set(APPOINTMENT_COLUMNS) | APPOINTMENT_DROPPED, "appointment"
    )
    _warn_on_new_fields(clinics, set(CLINIC_COLUMNS), "clinic")
    appt_rows = _to_tuples(
        appointments, APPOINTMENT_COLUMNS, APPOINTMENT_OPTIONAL, "Appointment"
    )
    clinic_rows = _to_tuples(clinics, CLINIC_COLUMNS, set(), "Clinic")

    appt_sql = (
        f"insert into raw_appointments ({', '.join(APPOINTMENT_COLUMNS)}, _run_id, _loaded_at)"
        f" values ({', '.join('?' * (len(APPOINTMENT_COLUMNS) + 2))})"
    )
    clinic_sql = (
        f"insert into raw_clinics ({', '.join(CLINIC_COLUMNS)}, _run_id, _loaded_at)"
        f" values ({', '.join('?' * (len(CLINIC_COLUMNS) + 2))})"
    )
    started = time.monotonic()
    con.execute("begin transaction")
    try:
        if appt_rows:
            con.executemany(appt_sql, [r + (run_id, loaded_at) for r in appt_rows])
        if clinic_rows:
            con.executemany(clinic_sql, [r + (run_id, loaded_at) for r in clinic_rows])
        con.execute("commit")
    except Exception:
        con.execute("rollback")
        raise
    log.info(
        "Loaded run %s: %s appointment rows, %s clinic rows (%.1fs)",
        run_id,
        len(appt_rows),
        len(clinic_rows),
        time.monotonic() - started,
    )
