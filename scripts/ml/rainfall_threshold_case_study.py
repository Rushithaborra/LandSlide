"""Case study: for the 68 Sikkim GSI events with a clean, single, precise
date, retrieve real historical rainfall strictly before the event and check
it against the backend's existing literature-sourced intensity-duration
threshold (app.services.alert_engine.intensity_duration_threshold -- reused,
not duplicated).

This is a validation exercise for the ALREADY-EXISTING rule-based alert
layer, not a new ML model, and its output is never joined into the
susceptibility training_dataset.csv (see build_training_dataset.py) --
keeping the two-layer architecture separate is a project requirement, not a
convenience.

Method note: the operational alert engine works on daily-granularity
rainfall (appropriate for live day-to-day monitoring). This case study uses
hourly-resolution historical data instead, so each event's exact timestamp
(where known) can be respected precisely, rather than rounding to a whole
calendar day -- verified during the audit to avoid same-day post-event
leakage.
"""
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from app.services.alert_engine import intensity_duration_threshold  # noqa: E402

from scripts.ml.ml_config import DEFAULT_CONFIG, MlConfig  # noqa: E402

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
DURATIONS_HOURS = {"24h": 24, "72h": 72, "7d": 24 * 7}
LOOKBACK_DAYS = 8


def extract_clean_dated_events(gsi_sikkim_csv) -> pd.DataFrame:
    """Same rule used in the data audit: keep only rows whose History field
    contains EXACTLY one parseable day+month+year date -- excludes year-only,
    multi-date, and blank History values rather than guessing among them."""
    df = pd.read_csv(gsi_sikkim_csv)

    def parse_single_date(hist):
        if pd.isna(hist):
            return None
        matches = []
        for part in str(hist).split(","):
            m = re.search(
                r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|"
                r"November|December)\s+(\d{4})",
                part,
                re.IGNORECASE,
            )
            if m:
                matches.append(m)
        if len(matches) != 1:
            return None
        m = matches[0]
        day, month, year = int(m.group(1)), m.group(2), int(m.group(3))
        event_dt = datetime.strptime(f"{day} {month} {year}", "%d %B %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", str(hist))
        time_assumed_midnight = tm is None
        if tm:
            event_dt = event_dt.replace(hour=int(tm.group(1)), minute=int(tm.group(2)))
        return event_dt, time_assumed_midnight

    parsed = df["History"].apply(parse_single_date)
    df = df[parsed.notna()].copy()
    df["event_datetime"] = [p[0] for p in parsed.dropna()]
    df["time_assumed_midnight"] = [p[1] for p in parsed.dropna()]
    return df[["Slide_No", "District", "Slide_Name", "Latitude", "Longitude", "History", "event_datetime",
               "time_assumed_midnight"]].reset_index(drop=True)


def cumulative_pre_event_rainfall(lat: float, lon: float, event_dt: datetime) -> dict[str, float]:
    start = (event_dt - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    end = event_dt.strftime("%Y-%m-%d")
    response = httpx.get(
        ARCHIVE_URL,
        params={"latitude": lat, "longitude": lon, "start_date": start, "end_date": end,
                "hourly": "precipitation", "timezone": "UTC"},
        timeout=30.0,
    )
    response.raise_for_status()
    data = response.json()["hourly"]
    times = [datetime.fromisoformat(t) for t in data["time"]]
    precip = data["precipitation"]
    pre_event = [(t, p) for t, p in zip(times, precip) if t < event_dt]  # strict: no post-event leakage

    result = {}
    for label, hours in DURATIONS_HOURS.items():
        cutoff = event_dt - timedelta(hours=hours)
        result[label] = sum(p for t, p in pre_event if t >= cutoff)
    return result


def run_case_study(config: MlConfig = DEFAULT_CONFIG) -> pd.DataFrame:
    events = extract_clean_dated_events(config.paths.gsi_sikkim_csv)
    print(f"{len(events)} clean single-dated Sikkim events found for the case study.")

    rows = []
    for _, ev in events.iterrows():
        rainfall = cumulative_pre_event_rainfall(ev["Latitude"], ev["Longitude"], ev["event_datetime"])
        threshold_1d = intensity_duration_threshold(1, risk_tier="moderate")
        threshold_3d = intensity_duration_threshold(3, risk_tier="moderate")
        threshold_7d = intensity_duration_threshold(7, risk_tier="moderate")
        rows.append({
            "Slide_No": ev["Slide_No"], "District": ev["District"], "Slide_Name": ev["Slide_Name"],
            "event_datetime": ev["event_datetime"], "time_assumed_midnight": ev["time_assumed_midnight"],
            "rain_24h_mm": rainfall["24h"], "rain_72h_mm": rainfall["72h"], "rain_7d_mm": rainfall["7d"],
            "threshold_1d_moderate_mm_per_day": threshold_1d,
            "threshold_3d_moderate_mm_per_day": threshold_3d * 3,
            "threshold_7d_moderate_mm_per_day": threshold_7d * 7,
            "crossed_24h": rainfall["24h"] >= threshold_1d,
            "crossed_72h": rainfall["72h"] >= threshold_3d * 3,
            "crossed_7d": rainfall["7d"] >= threshold_7d * 7,
        })

    result = pd.DataFrame(rows)
    result["crossed_any_window"] = result[["crossed_24h", "crossed_72h", "crossed_7d"]].any(axis=1)

    config.paths.case_study_csv.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(config.paths.case_study_csv, index=False)

    n = len(result)
    print(f"\nEvents where pre-event rainfall crossed the moderate-tier threshold "
          f"in at least one window: {result['crossed_any_window'].sum()}/{n} "
          f"({result['crossed_any_window'].mean() * 100:.1f}%)")
    print(f"saved -> {config.paths.case_study_csv}")
    print("\nThis is a threshold-validation case study, NOT part of the susceptibility "
          "training dataset. It stays in data/case_study/, never joined to training_dataset.csv.")
    return result


if __name__ == "__main__":
    run_case_study()
