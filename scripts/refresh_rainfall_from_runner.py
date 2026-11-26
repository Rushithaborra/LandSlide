"""Fetch rainfall from Open-Meteo HERE and hand it to the backend.

Run by .github/workflows/rainfall-refresh.yml. Open-Meteo rate-limits (HTTP 429)
the shared outgoing IPs of free hosts such as Render, so the backend's own fetch
can fail; a GitHub Actions runner fetches instead, and the backend does the same
storing and alert logic it always does (POST /rainfall/ingest).

Standard library only, so the workflow needs no install step.

    OFFICER_KEY=... BACKEND_URL=https://... python scripts/refresh_rainfall_from_runner.py [--no-alerts] [--full] [--force]

Open-Meteo's free tier allows 10,000 calls a day, 5,000 an hour, 600 a minute, and
every location in a multi-location request counts as a call -- weighted up when the
request spans more than 14 days. The old 23-day request (20 past + 3 forecast) cost
~1.6 calls per zone, so 800 zones every hour was ~31,000 calls a day: the daily limit
ran out part-way through the day and the remaining runs failed with HTTP 429.
The workflow is also started twice an hour (GitHub's schedule plus cron-job.org).
So now:
- a run only fetches when the stored rainfall is at least MIN_AGE_MINUTES old
  (GET /rainfall/status); otherwise it exits green without touching Open-Meteo.
  Triggers can stay frequent (they are what makes a fetch happen on time) while
  real fetches happen about every 3 hours. --force skips this check.
- most fetches use a SHORT window (the last few days, 1 call per zone); the backend
  judges alerts on its stored history plus these fresh days.
- the first fetch of each UTC day (or --full) refetches the whole 20-day window,
  which also picks up Open-Meteo's revisions of older days and backfills newly
  selected zones.
That is ~1 full + ~7 short fetches a day, about 7,000 calls for 800 zones.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

OPEN_METEO_URL = os.environ.get("OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast")
CHUNK_SIZE = 25  # locations per Open-Meteo request
FULL_PAST_DAYS = 20  # the backend's own window (covers the longest alert window)
SHORT_PAST_DAYS = 2  # yesterday and the day before: still settling in the model data
FORECAST_DAYS = 3
MIN_AGE_MINUTES = 170  # fetch only when stored rainfall is at least this old (~every 3 h with hourly triggers)
FULL_WINDOW_UTC_HOURS = 3  # the fetch that lands in the first 3 UTC hours of a day is the full one
RATE_LIMITED_PREFIX = "rate-limited: "
GRID_DEGREES = 0.01  # zones closer than this (~1 km) share one Open-Meteo point; every model cell is far larger
ROTATE_CHUNKS_PER_HOUR = 3  # how far the starting point moves each hour (see rotate_for_fairness)


class RateLimited(RuntimeError):
    """Open-Meteo's hourly or daily allowance is used up ("...try again in the next hour").
    Retrying inside this run cannot help, so it is not retried."""


def rotate_for_fairness(targets: list[dict], hour: int) -> list[dict]:
    """Start the list at a different place each hour. When the hourly limit stops a run
    part-way, the zones at the END of the list go without; with a fixed order that is
    the same states (the log showed Nagaland and part of Mizoram) every time."""
    if not targets:
        return targets
    shift = (hour * ROTATE_CHUNKS_PER_HOUR * CHUNK_SIZE) % len(targets)
    return targets[shift:] + targets[:shift]


def dedupe_points(targets: list[dict]) -> list[dict]:
    """One fetch point per ~1 km cell: [{"lat", "lng", "zone_ids": [...]}, ...] in first-seen
    order. Open-Meteo's models have 2-25 km cells, so zones this close get identical
    rainfall anyway, and each duplicate would cost a call."""
    points: dict[tuple[int, int], dict] = {}
    for t in targets:
        key = (round(t["lat"] / GRID_DEGREES), round(t["lng"] / GRID_DEGREES))
        if key not in points:
            points[key] = {"lat": t["lat"], "lng": t["lng"], "zone_ids": []}
        points[key]["zone_ids"].append(t["id"])
    return list(points.values())


def call(url: str, *, data: dict | None = None, headers: dict | None = None, attempts: int = 4, timeout: int = 90):
    """JSON request with retries. Retries cover a Render server waking up (~50 s)
    and Open-Meteo's occasional 429/5xx (a per-minute 429 clears in a minute; an
    hourly or daily one does not, so that raises RateLimited at once); anything else
    fails immediately."""
    body = json.dumps(data).encode() if data is not None else None
    req_headers = {"Content-Type": "application/json", **(headers or {})}
    for attempt in range(1, attempts + 1):
        try:
            req = urllib.request.Request(url, data=body, headers=req_headers, method="POST" if body is not None else "GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            retryable = e.code == 429 or e.code >= 500
            detail = e.read().decode(errors="replace")[:200]
            if e.code == 429 and re.search(r"\b(hourly|daily)\b", detail, re.IGNORECASE):
                raise RateLimited(f"HTTP 429 from {urllib.parse.urlsplit(url).netloc}: {detail}") from None
            if not retryable or attempt == attempts:
                raise RuntimeError(f"HTTP {e.code} from {urllib.parse.urlsplit(url).netloc}: {detail}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == attempts:
                raise RuntimeError(f"{urllib.parse.urlsplit(url).netloc} unreachable: {e}") from None
        time.sleep(15 * attempt)


def fetch_chunk(points: list[dict], past_days: int) -> list[dict]:
    """One Open-Meteo request for up to CHUNK_SIZE points -> one ingest entry per zone."""
    query = urllib.parse.urlencode(
        {
            "latitude": ",".join(str(p["lat"]) for p in points),
            "longitude": ",".join(str(p["lng"]) for p in points),
            "daily": "precipitation_sum",
            "past_days": past_days,
            "forecast_days": FORECAST_DAYS,
            "timezone": "UTC",
        }
    )
    payload = call(f"{OPEN_METEO_URL}?{query}")
    locations = [payload] if isinstance(payload, dict) else payload
    if len(locations) != len(points):
        raise RuntimeError(f"Open-Meteo returned {len(locations)} locations for {len(points)} points")
    readings = []
    for p, loc in zip(points, locations):
        # A day Open-Meteo has no value for (null) is skipped, as in the backend.
        days = [{"day": d, "mm": mm} for d, mm in zip(loc["daily"]["time"], loc["daily"]["precipitation_sum"]) if mm is not None]
        readings.extend({"zone_id": zone_id, "days": days} for zone_id in p["zone_ids"])
    return readings


def exit_code_for(result: dict, failures: list[str]) -> int:
    """0 only if the run actually left the backend with fresher data. A run
    that fetched successfully from Open-Meteo but ends with the backend
    reporting zones_refreshed=0 (e.g. the runner's target list no longer
    matches the backend's own re-selection by the time it posts, minutes
    later) must show red, not green -- a silent "success" here is exactly
    the kind of gap that let a real stale-data incident go unnoticed.

    A run that stored data but was cut short ONLY by Open-Meteo's hourly/daily
    limit is green with a warning: the zones it skipped go first next run
    (rotate_for_fairness), and a red run (plus an email) every time the quota
    is tight hid the failures that need a person. Any other chunk failure is red."""
    if result.get("zones_refreshed", 0) == 0:
        return 1
    other = [f for f in failures if not f.startswith(RATE_LIMITED_PREFIX)]
    return 1 if other else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--no-alerts", action="store_true", help="store rainfall only; don't trigger alerts/SMS")
    parser.add_argument("--full", action="store_true", help=f"fetch the full {FULL_PAST_DAYS}-day window (normally once a day)")
    parser.add_argument("--force", action="store_true", help=f"fetch even if the stored rainfall is under {MIN_AGE_MINUTES} min old")
    args = parser.parse_args()
    full = args.full or time.gmtime().tm_hour < FULL_WINDOW_UTC_HOURS
    past_days = FULL_PAST_DAYS if full else SHORT_PAST_DAYS

    backend = os.environ.get("BACKEND_URL", "").rstrip("/")
    key = os.environ.get("OFFICER_KEY", "")
    if not backend or not key:
        print("BACKEND_URL and OFFICER_KEY must be set", file=sys.stderr)
        return 2
    auth = {"X-API-Key": key}

    status = call(f"{backend}/rainfall/status", attempts=5, timeout=120)  # first call wakes the server
    age = status.get("age_minutes")
    if not args.force and age is not None and age < MIN_AGE_MINUTES:
        print(f"Rainfall was refreshed {age} min ago (fetching from {MIN_AGE_MINUTES} min); skipping to save Open-Meteo quota.")
        return 0

    targets = call(f"{backend}/rainfall/targets", headers=auth, attempts=5, timeout=120)
    targets = rotate_for_fairness(targets, int(time.time() // 3600))
    points = dedupe_points(targets)
    print(f"{len(targets)} zones to refresh as {len(points)} Open-Meteo points, {past_days} past days ({'full' if full else 'short'} run)")

    readings, failures = [], []
    for i in range(0, len(points), CHUNK_SIZE):
        chunk = points[i : i + CHUNK_SIZE]
        try:
            readings.extend(fetch_chunk(chunk, past_days))
        except RateLimited as e:
            failures.append(f"{RATE_LIMITED_PREFIX}{e}")
            skipped = sum(len(p["zone_ids"]) for p in points[i:])
            print(f"::warning::Open-Meteo's limit is used up: skipping the last {skipped} zones until the next run ({e})", file=sys.stderr)
            break
        except RuntimeError as e:
            failures.append(str(e))
            print(f"  chunk {i // CHUNK_SIZE + 1} failed: {e}", file=sys.stderr)
        time.sleep(1)  # stay well under the per-minute limit

    if not readings:
        print("Nothing could be fetched from Open-Meteo; not calling the backend.", file=sys.stderr)
        return 1

    result = call(
        f"{backend}/rainfall/ingest?alerts={'false' if args.no_alerts else 'true'}",
        data={"readings": readings},
        headers=auth,
        timeout=180,
    )
    print(json.dumps({k: v for k, v in result.items() if k != "errors"}))
    if result.get("errors"):
        print("backend reported:", result["errors"], file=sys.stderr)
    if result.get("zones_refreshed", 0) == 0:
        print(
            f"::error::Fetched data for {len(readings)} zones from Open-Meteo, but the backend recorded "
            "0 as refreshed -- nothing was actually stored, so this run must not show green.",
            file=sys.stderr,
        )
    return exit_code_for(result, failures)


if __name__ == "__main__":
    sys.exit(main())
