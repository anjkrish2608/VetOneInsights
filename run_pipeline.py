"""Nordvet no-show pipeline: single entry point.

Run:  python run_pipeline.py

1. Ingest: if raw is empty, backfill from BACKFILL_FROM; otherwise fetch only
   appointments changed since the newest updated_at already loaded.
2. (Next step) dbt build: staging and marts on top of the raw tables.

Settings come from environment variables (.env); see .env.example.
"""

import logging
import os
import sys
import time
from datetime import UTC, date, datetime, timedelta

from dotenv import load_dotenv

from ingestion import load_raw, vetone_client

log = logging.getLogger("run_pipeline")

BACKFILL_DAYS_AHEAD = 90  # past every existing future booking (D-backfill)
REQUIRED_SETTINGS = [
    "VETONE_BASE_URL",
    "VETONE_CLIENT_ID",
    "VETONE_CLIENT_SECRET",
    "DUCKDB_PATH",
    "BACKFILL_FROM",
]


def read_settings() -> dict[str, str]:
    """Read required settings from the environment; fail listing any that are missing."""
    load_dotenv()
    missing = [name for name in REQUIRED_SETTINGS if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            f"Missing settings in .env: {', '.join(missing)} (see .env.example)"
        )
    return {name: os.environ[name] for name in REQUIRED_SETTINGS}


def ingest(settings: dict[str, str], run_id: str, loaded_at: datetime) -> None:
    """Fetch clinics and new/changed appointments, then append them to raw in one transaction."""
    con = load_raw.connect(settings["DUCKDB_PATH"])
    try:
        watermark = load_raw.get_watermark(con)
        api = vetone_client.connect(
            settings["VETONE_BASE_URL"],
            settings["VETONE_CLIENT_ID"],
            settings["VETONE_CLIENT_SECRET"],
        )
        clinics = vetone_client.fetch_clinics(api)

        if watermark is None:
            date_to = (date.today() + timedelta(days=BACKFILL_DAYS_AHEAD)).isoformat()
            log.info(
                "Raw is empty: backfilling %s..%s", settings["BACKFILL_FROM"], date_to
            )
            appointments = vetone_client.fetch_appointments(
                api, date_from=settings["BACKFILL_FROM"], date_to=date_to
            )
            if not appointments:
                log.warning("Backfill returned 0 appointments; check BACKFILL_FROM")
            elif max(a["scheduled_at"][:10] for a in appointments) >= date_to:
                log.warning(
                    "Bookings reach the end of the backfill window; raise BACKFILL_DAYS_AHEAD"
                )
        else:
            log.info("Incremental run: appointments updated since %s", watermark)
            appointments = vetone_client.fetch_appointments(
                api, updated_since=watermark
            )

        load_raw.load_run(con, appointments, clinics, run_id, loaded_at)
        total, distinct = con.execute(
            "select count(*), count(distinct id) from raw_appointments"
        ).fetchone()
        log.info(
            "raw_appointments now holds %s rows (%s distinct appointments)",
            total,
            distinct,
        )
    finally:
        con.close()


def main() -> None:
    """Run the pipeline end to end; exit with status 1 on any failure."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    started = time.monotonic()
    loaded_at = datetime.now(UTC).replace(tzinfo=None)  # stored as UTC
    run_id = loaded_at.strftime("%Y%m%dT%H%M%SZ")
    log.info("Pipeline run %s started", run_id)
    try:
        settings = read_settings()
        ingest(settings, run_id, loaded_at)
    except Exception:
        log.exception("Pipeline run %s FAILED; raw data is unchanged", run_id)
        sys.exit(1)
    log.info("Pipeline run %s finished in %.1fs", run_id, time.monotonic() - started)


if __name__ == "__main__":
    main()
