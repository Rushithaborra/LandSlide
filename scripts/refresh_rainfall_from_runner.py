"""Fetch rainfall from Open-Meteo HERE and hand it to the backend.

Run by .github/workflows/rainfall-refresh.yml. Open-Meteo rate-limits (HTTP 429)
the shared outgoing IPs of free hosts such as Render, so the backend's own fetch
can fail; a GitHub Actions runner fetches instead, and the backend does the same
storing and alert logic it always does (POST /rainfall/ingest).

Standard library only, so the workflow needs no install step.

    OFFICER_KEY=... BACKEND_URL=https://... python scripts/refresh_rainfall_from_runner.py [--no-alerts]
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

OPEN_METEO_URL = os.environ.get("OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast")
CHUNK_SIZE = 25  # locations per Open-Meteo request
PAST_DAYS, FORECAST_DAYS = 20, 3  # same window the backend uses (covers the longest alert window)


def call(url: str, *, data: dict | None = None, headers: dict | None = None, attempts: int = 4, timeout: int = 90):
    """JSON request with retries. Retries cover a Render server waking up (~50 s)
    and Open-Meteo's occasional 429/5xx; anything else fails immediately."""
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
            if not retryable or attempt == attempts:
                raise RuntimeError(f"HTTP {e.code} from {urllib.parse.urlsplit(url).netloc}: {detail}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == attempts:
                raise RuntimeError(f"{urllib.parse.urlsplit(url).netloc} unreachable: {e}") from None
        time.sleep(15 * attempt)


def fetch_chunk(targets: list[dict]) -> list[dict]:
    """One Open-Meteo request for up to CHUNK_SIZE zones -> one ingest entry each."""
    query = urllib.parse.urlencode(
        {
            "latitude": ",".join(str(t["lat"]) for t in targets),
            "longitude": ",".join(str(t["lng"]) for t in targets),
            "daily": "precipitation_sum",
            "past_days": PAST_DAYS,
            "forecast_days": FORECAST_DAYS,
            "timezone": "UTC",
        }
    )
    payload = call(f"{OPEN_METEO_URL}?{query}")
    locations = [payload] if isinstance(payload, dict) else payload
    if len(locations) != len(targets):
        raise RuntimeError(f"Open-Meteo returned {len(locations)} locations for {len(targets)} points")
    return [
        {
            "zone_id": t["id"],
            # A day Open-Meteo has no value for (null) is skipped, as in the backend.
            "days": [{"day": d, "mm": mm} for d, mm in zip(loc["daily"]["time"], loc["daily"]["precipitation_sum"]) if mm is not None],
        }
        for t, loc in zip(targets, locations)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--no-alerts", action="store_true", help="store rainfall only; don't trigger alerts/SMS")
    args = parser.parse_args()

    backend = os.environ.get("BACKEND_URL", "").rstrip("/")
    key = os.environ.get("OFFICER_KEY", "")
    if not backend or not key:
        print("BACKEND_URL and OFFICER_KEY must be set", file=sys.stderr)
        return 2
    auth = {"X-API-Key": key}

    targets = call(f"{backend}/rainfall/targets", headers=auth, attempts=5, timeout=120)  # first call wakes the server
    print(f"{len(targets)} zones to refresh")

    readings, failures = [], []
    for i in range(0, len(targets), CHUNK_SIZE):
        chunk = targets[i : i + CHUNK_SIZE]
        try:
            readings.extend(fetch_chunk(chunk))
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
    return 1 if failures else 0  # a partially-failed run is stored, but shows red so it gets noticed


if __name__ == "__main__":
    sys.exit(main())
