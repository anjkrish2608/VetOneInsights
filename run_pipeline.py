"""Nordvet no-show pipeline: single entry point.

Run:  python run_pipeline.py

1. Ingest: if raw is empty, backfill from BACKFILL_FROM; otherwise fetch only
   appointments changed since the newest updated_at already loaded.
2. dbt build: staging and marts on top of the raw tables, plus all data tests.

Settings come from environment variables (.env); see .env.example.
Run from the repo root: DUCKDB_PATH is relative to it, for Python and dbt alike.
"""

import json
import logging
import os
import pathlib
import shutil
import subprocess
import sys
import time
from datetime import UTC, date, datetime, timedelta

from dotenv import load_dotenv

from ingestion import load_raw, vetone_client

log = logging.getLogger("run_pipeline")

DBT_PROJECT_DIR = pathlib.Path(__file__).resolve().parent / "nordvet_dbt"

# Days AHEAD of today the backfill reaches, to capture existing future bookings.
# Not history: history starts at BACKFILL_FROM (D-backfill).
BACKFILL_DAYS_AHEAD = 90
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
            elif not any(a.get("deleted_at") for a in appointments):
                # A normal backfill includes hundreds of deleted appointments (API note 1),
                # so none at all suggests include_deleted has stopped working.
                log.warning(
                    "Backfill has no deleted appointments; include_deleted may have "
                    "stopped working, so deleted ones would be counted (D-api-change)"
                )
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
        con.close()  # DuckDB allows one writer: release the file before dbt opens it


def _dbt(dbt: str, command: list[str]) -> int:
    """Run one dbt command (e.g. ["build"]) against the project; return its exit code."""
    return subprocess.run(
        [
            dbt,
            *command,
            "--project-dir",
            str(DBT_PROJECT_DIR),
            "--profiles-dir",
            str(DBT_PROJECT_DIR),
        ],
        check=False,
    ).returncode


def run_dbt() -> None:
    """Check source freshness, then run `dbt build`; raise if anything fails (D-dbt-run)."""
    # Use the dbt installed next to this Python, so the venv's pinned dbt is used
    # even if the venv isn't activated.
    dbt = shutil.which("dbt", path=os.path.dirname(sys.executable))
    if dbt is None:
        raise RuntimeError(
            "dbt not found in this Python environment; pip install -r requirements.txt"
        )
    started = time.monotonic()

    # Freshness only warns (D-api-change): a stale source is worth a loud log line,
    # but a long holiday weekend shouldn't block the morning report.
    log.info("Checking source freshness")
    if _dbt(dbt, ["source", "freshness"]) != 0:
        raise RuntimeError("dbt source freshness failed; see dbt output above")
    results = json.loads((DBT_PROJECT_DIR / "target" / "sources.json").read_text())
    for source in results["results"]:
        if source["status"] != "pass":
            log.warning(
                "VetOne data looks stale: newest change is %.0f hours old (%s). "
                "updated_since or paging may have changed (D-api-change)",
                source["max_loaded_at_time_ago_in_s"] / 3600,
                source["unique_id"],
            )

    log.info("Running dbt build")
    exit_code = _dbt(dbt, ["build"])
    if exit_code != 0:
        raise RuntimeError(
            f"dbt build failed (exit code {exit_code}); see dbt output above. "
            "This run's raw rows are loaded; fix the cause and re-run."
        )
    log.info("dbt freshness and build passed in %.1fs", time.monotonic() - started)


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
        run_dbt()
    except Exception:
        log.exception("Pipeline run %s FAILED", run_id)
        sys.exit(1)
    log.info("Pipeline run %s finished in %.1fs", run_id, time.monotonic() - started)


if __name__ == "__main__":
    main()
