"""VetOne API client: authentication, error handling and pagination.

Plain functions. The connection is a small dict holding the base URL, the
credentials and the current token, so a 401 can swap in a fresh token.
Decisions referenced below (D-...) are explained in DECISIONS.md.
"""

import logging
import time
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime

import requests

log = logging.getLogger(__name__)

PAGE_LIMIT = (
    500  # the API's real maximum; higher values are silently capped (D-backfill)
)
TIMEOUT_SECONDS = 60  # the first call can take ~20s while the API wakes up
MAX_SERVER_RETRIES = 4  # 5xx and network errors: pauses of 2, 4, 8, 16s (D-errors)
MAX_RATE_LIMIT_WAITS = 20  # 429s: give up if the API keeps saying "slow down"
MAX_PAGES = (
    1000  # safety stop (500,000 rows): a bug must not loop forever on a live API
)


def _retry_after_seconds(value: str | None) -> int:
    """Seconds to wait from a Retry-After header: seconds or an HTTP date (D-api-change)."""
    if value is None:
        return 5
    try:
        return max(0, int(value))
    except ValueError:
        pass
    try:
        wait = parsedate_to_datetime(value) - datetime.now(UTC)
        return max(0, int(wait.total_seconds()) + 1)
    except (TypeError, ValueError):
        log.warning("Retry-After %r is neither seconds nor a date; waiting 5s", value)
        return 5


def _records(body: object, path: str) -> list[dict]:
    """Return the rows under 'data'; fail clearly if the response shape has changed."""
    if not isinstance(body, dict) or not isinstance(body.get("data"), list):
        shape = sorted(body) if isinstance(body, dict) else type(body).__name__
        raise TypeError(
            f"VetOne {path} response has no 'data' list (got {shape}); "
            "the API format may have changed (D-api-change)"
        )
    return body["data"]


def _send(method: str, url: str, **kwargs) -> requests.Response:
    """Send one request, retrying 429s and transient server/network errors.

    Returns the final response; any status other than 429/5xx is returned as is,
    so the caller decides what it means.
    """
    server_errors = 0
    rate_limit_waits = 0
    while True:
        try:
            resp = requests.request(method, url, timeout=TIMEOUT_SECONDS, **kwargs)
        except (requests.ConnectionError, requests.Timeout) as exc:
            resp = None
            reason = type(exc).__name__
        else:
            reason = f"HTTP {resp.status_code}"

        if resp is not None and resp.status_code == 429:
            rate_limit_waits += 1
            if rate_limit_waits > MAX_RATE_LIMIT_WAITS:
                return resp
            wait = _retry_after_seconds(resp.headers.get("Retry-After"))
            log.warning("Rate limited (429); waiting %ss as Retry-After asks", wait)
            time.sleep(wait)
            continue

        if resp is None or resp.status_code >= 500:
            server_errors += 1
            if server_errors > MAX_SERVER_RETRIES:
                if resp is None:
                    raise RuntimeError(
                        f"VetOne unreachable after {MAX_SERVER_RETRIES} retries ({reason})"
                    )
                return resp
            pause = 2**server_errors
            log.warning(
                "%s from VetOne; retry %s/%s in %ss",
                reason,
                server_errors,
                MAX_SERVER_RETRIES,
                pause,
            )
            time.sleep(pause)
            continue

        return resp


def get_token(base_url: str, client_id: str, client_secret: str) -> str:
    """Exchange client credentials for a bearer token (valid about 60 minutes)."""
    resp = _send(
        "POST",
        f"{base_url}/auth/token",
        json={"client_id": client_id, "client_secret": client_secret},
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"VetOne login failed: HTTP {resp.status_code} {resp.text[:200]}"
        )
    body = resp.json()
    if not isinstance(body, dict) or "access_token" not in body:
        shape = sorted(body) if isinstance(body, dict) else type(body).__name__
        raise RuntimeError(
            f"VetOne login response has no 'access_token' (got {shape}); "
            "the API format may have changed (D-api-change)"
        )
    return body["access_token"]


def connect(base_url: str, client_id: str, client_secret: str) -> dict:
    """Log in and return a connection dict used by the other functions."""
    base_url = base_url.rstrip("/")
    started = time.monotonic()
    token = get_token(base_url, client_id, client_secret)
    log.info("Logged in to VetOne in %.1fs", time.monotonic() - started)
    return {
        "base_url": base_url,
        "client_id": client_id,
        "client_secret": client_secret,
        "token": token,
    }


def get_json(api: dict, path: str, params: dict | None = None) -> dict:
    """GET a JSON endpoint. On a 401, fetch a new token and retry once (D-errors)."""
    token_refreshed = False
    while True:
        resp = _send(
            "GET",
            f"{api['base_url']}{path}",
            headers={"Authorization": f"Bearer {api['token']}"},
            params=params,
        )
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 401 and not token_refreshed:
            log.warning("401 on %s; fetching a new token and retrying once", path)
            api["token"] = get_token(
                api["base_url"], api["client_id"], api["client_secret"]
            )
            token_refreshed = True
            continue
        raise RuntimeError(
            f"VetOne GET {path} failed: HTTP {resp.status_code} {resp.text[:300]}"
        )


def fetch_clinics(api: dict) -> list[dict]:
    """Return all clinics (one page; the endpoint is not paginated)."""
    body = get_json(api, "/v1/clinics")
    if body.get("next_cursor"):
        raise RuntimeError(
            "/v1/clinics returned a next_cursor; pagination is not handled for clinics"
        )
    rows = _records(body, "/v1/clinics")
    log.info("Fetched %s clinics", len(rows))
    return rows


def _check_window(
    date_from: str | None, date_to: str | None, updated_since: str | None
) -> None:
    """Reject parameter combinations the API would silently get wrong (D-validate)."""
    if updated_since is not None:
        if date_from is not None or date_to is not None:
            raise ValueError("Use either updated_since or from/to, not both")
        try:
            parsed = datetime.fromisoformat(updated_since)
        except ValueError:
            raise ValueError(
                f"updated_since is not an ISO 8601 timestamp: {updated_since!r}"
            ) from None
        if parsed.tzinfo is None:
            raise ValueError(
                f"updated_since needs a timezone (e.g. 'Z'): {updated_since!r}"
            )
        return
    if date_from is None or date_to is None:
        raise ValueError(
            "from and to must be sent together; one alone changes the window a lot"
        )
    try:
        start, end = date.fromisoformat(date_from), date.fromisoformat(date_to)
    except ValueError:
        raise ValueError(
            f"from/to must be YYYY-MM-DD dates: {date_from!r}, {date_to!r}"
        ) from None
    if start > end:
        raise ValueError(
            f"from ({date_from}) is after to ({date_to}); the API would return 0 rows"
        )


def fetch_appointments(
    api: dict,
    date_from: str | None = None,
    date_to: str | None = None,
    updated_since: str | None = None,
) -> list[dict]:
    """Fetch all pages of appointments, including deleted ones.

    Pass either date_from + date_to (backfill, inclusive local dates) or
    updated_since (daily incremental). Returns the rows exactly as the API sent them.
    """
    _check_window(date_from, date_to, updated_since)
    params: dict = {
        "limit": PAGE_LIMIT,
        "include_deleted": "true",
    }  # only "true" works (D-deleted)
    if updated_since is not None:
        params["updated_since"] = updated_since
    else:
        params["from"], params["to"] = date_from, date_to

    started = time.monotonic()
    rows: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        body = get_json(api, "/v1/appointments", params)
        page_rows = _records(body, "/v1/appointments")
        rows.extend(page_rows)
        log.debug("Page %s: %s rows", page, len(page_rows))
        # VetOne always sends next_cursor, as null on the last page. If the key is gone,
        # paging has changed: stop, rather than load one page and call it complete.
        if "next_cursor" not in body:
            raise RuntimeError(
                "VetOne /v1/appointments response has no 'next_cursor' key; paging may "
                "have changed, so stopping instead of loading a partial pull (D-api-change)"
            )
        cursor = body["next_cursor"]
        if not cursor:
            if len(page_rows) == PAGE_LIMIT:
                log.warning(
                    "Last page was full (%s rows) but had no next_cursor. Usually fine, "
                    "but if it repeats, paging may have changed (D-api-change)",
                    PAGE_LIMIT,
                )
            break
        # The cursor carries the original filters; extra params are ignored by the API.
        params = {"cursor": cursor}
    else:
        raise RuntimeError(f"Stopped after {MAX_PAGES} pages; refusing to keep paging")

    log.info(
        "Fetched %s appointments in %s pages (%.1fs) for %s",
        len(rows),
        page,
        time.monotonic() - started,
        f"updated_since={updated_since}"
        if updated_since
        else f"{date_from}..{date_to}",
    )
    return rows
