"""Log IMD's real rain-gauge readings for the north-east alongside Open-Meteo's
estimate at the same coordinates, one poll at a time, into a local SQLite file.

Purpose: after a few weeks of polls, `scripts/imd_station_comparison.py` can give a
real, point-to-point answer to "how much does Open-Meteo actually disagree with IMD's
own gauges here" -- something the project has so far only checked with a rough,
one-shot, not-quite-comparable pass (district averages vs single hill points).

    python scripts/imd_station_logger.py

Needs IMD_API_KEY/IMD_EMAIL/IMD_PASSWORD in .env, so it can only run from this
machine (IMD's key is bound to one registered IP -- see app/services/imd.py). That
also means it cannot run on GitHub Actions; schedule it locally instead, e.g. Windows
Task Scheduler running this every few hours (`docs/imd_station_logging.md` has the
exact steps). Each run is one IMD API call (all-India, filtered to the north-east
client-side) plus a few Open-Meteo calls; safe to run often.

Output: data/interim/imd_station_log.db (gitignored -- this is a local research
artifact, not part of the deployed system), table `polls`, one row per station per
run. Nothing here touches the production database or dashboard.
"""
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import imd, open_meteo

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "interim" / "imd_station_log.db"
NE_STATES = {"ASSAM", "MEGHALAYA", "MANIPUR", "MIZORAM", "NAGALAND", "TRIPURA", "SIKKIM", "ARUNACHAL PRADESH"}
OPEN_METEO_BATCH = 50  # matches the scale already verified fast in app/services/open_meteo.py's own docstring

SCHEMA = """
CREATE TABLE IF NOT EXISTS polls (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    polled_at_utc     TEXT NOT NULL,       -- when THIS script ran, not IMD's own timestamp
    station_id        TEXT NOT NULL,
    station_name      TEXT,
    district          TEXT,
    state             TEXT NOT NULL,
    lat               REAL NOT NULL,
    lng               REAL NOT NULL,
    imd_date          TEXT,                -- IMD's own observation date/time, as reported
    imd_time          TEXT,
    imd_rainfall_mm    REAL,               -- IMD's raw RAINFALL field; its accumulation period is not documented by IMD
    open_meteo_today_mm REAL               -- Open-Meteo's running total for today at these exact coordinates
);
"""


def to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def poll() -> int:
    try:
        stations_all = imd.call("aws_data")
    except imd.ImdNotConfigured as e:
        print(f"not configured: {e}", file=sys.stderr)
        return 2
    except imd.ImdError as e:
        print(f"IMD error: {e}", file=sys.stderr)
        return 1

    stations = [
        s for s in stations_all
        if (s.get("STATE") or "").strip().upper() in NE_STATES and to_float(s.get("Latitude")) is not None and to_float(s.get("Longitude")) is not None
    ]
    print(f"{len(stations_all)} stations returned by IMD; {len(stations)} in the north-east with usable coordinates")
    if not stations:
        return 1

    points = [(to_float(s["Latitude"]), to_float(s["Longitude"])) for s in stations]
    today_mm: list[float | None] = []
    for i in range(0, len(points), OPEN_METEO_BATCH):
        batch = points[i : i + OPEN_METEO_BATCH]
        series = open_meteo.fetch_daily_rainfall_batch(batch, past_days=1, forecast_days=0)
        # fetch_daily_rainfall_batch drops null days; "today" is the series' last entry, if any.
        today_mm.extend(s[-1].intensity_mm if s else None for s in series)

    polled_at = datetime.now(timezone.utc).isoformat()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(SCHEMA)
        conn.executemany(
            "INSERT INTO polls (polled_at_utc, station_id, station_name, district, state, lat, lng, "
            "imd_date, imd_time, imd_rainfall_mm, open_meteo_today_mm) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    polled_at, s["ID"], s.get("STATION"), s.get("DISTRICT"), s["STATE"].title(),
                    lat, lng, s.get("DATE"), s.get("TIME"), to_float(s.get("RAINFALL")), om_mm,
                )
                for s, (lat, lng), om_mm in zip(stations, points, today_mm)
            ],
        )
        conn.commit()
        total_polls = conn.execute("SELECT COUNT(*) FROM polls").fetchone()[0]
    finally:
        conn.close()
    print(f"logged {len(stations)} station readings to {DB_PATH} ({total_polls} rows total across all polls so far)")
    return 0


if __name__ == "__main__":
    sys.exit(poll())
