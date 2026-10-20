"""How much do the long (10-20 day) windows of Sikkim's rainfall rule add, and what do they cost?

For each of the 68 clean single-dated GSI Sikkim landslides, take real historical daily rain at
the exact spot (Open-Meteo archive) and test the live rule -- the same thresholds, via
app.services.alert_engine.intensity_duration_threshold -- capped at different longest windows:

  recall           did the rule already say "alert" on the day BEFORE the slide? (strictly pre-event)
  alert-day rate   on ordinary days at those same spots, how often is the rule alerting at all?

Together they show what each extra window buys (events caught) and costs (days alerting). This is
validation of the rule-based layer only, never joined to the susceptibility training data.

Caveats the output repeats: 68 events is a small sample; GSI records are incomplete, so an
"ordinary" day may hide an unrecorded slide (the alert-day rate is not a true false-alarm rate);
Open-Meteo's archive is reanalysis, coarser than a mountain slope; moderate tier is used throughout
(the events have no assigned risk tier); only Sikkim has a landslide-specific threshold.
"""
import sys
import time
from datetime import timedelta
from pathlib import Path

import httpx
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from app.config import get_rainfall_threshold  # noqa: E402
from app.services.alert_engine import intensity_duration_threshold  # noqa: E402

from scripts.ml.ml_config import DEFAULT_CONFIG  # noqa: E402
from scripts.ml.rainfall_threshold_case_study import ARCHIVE_URL, extract_clean_dated_events  # noqa: E402

STATE, TIER = "Sikkim", "moderate"
MONSOON = (6, 7, 8, 9)
EXCLUDE_DAYS_AROUND_EVENT = 3  # keep the days right around a slide out of the "ordinary days" pool


def daily_rain(lat: float, lon: float, year: int) -> pd.Series:
    """Daily precipitation (mm) for the event's year, plus December before it (20 days of history)."""
    params = {
        "latitude": lat, "longitude": lon, "daily": "precipitation_sum", "timezone": "UTC",
        "start_date": f"{year - 1}-12-01", "end_date": f"{year}-12-31",
    }
    for attempt in range(4):
        response = httpx.get(ARCHIVE_URL, params=params, timeout=60.0)
        if response.status_code != 429:
            response.raise_for_status()
            d = response.json()["daily"]
            return pd.Series(d["precipitation_sum"], index=pd.to_datetime(d["time"]), dtype="float64")
        time.sleep(5 * (attempt + 1))
    response.raise_for_status()


def alerting(rain: pd.Series, durations: list[int], config) -> pd.Series:
    """True on each day where ANY window's mean rain (ending that day) is at or over its threshold --
    the engine's rule (evaluate_daily_rainfall), computed for every day at once."""
    flags = pd.Series(False, index=rain.index)
    for d in durations:
        mean = rain.rolling(d, min_periods=d).mean()
        flags |= mean >= intensity_duration_threshold(d, config, TIER)
    return flags


def run() -> pd.DataFrame:
    config = get_rainfall_threshold(STATE)
    caps = sorted(config.durations_days)
    events = extract_clean_dated_events(DEFAULT_CONFIG.paths.gsi_sikkim_csv)
    print(f"{len(events)} events; windows tested (days): {caps}; thresholds from the live {STATE} rule, {TIER} tier\n")

    per_event = []
    ordinary = {cap: [] for cap in caps}  # per-event fraction of ordinary monsoon days alerting
    for i, ev in events.iterrows():
        event_day = pd.Timestamp(ev["event_datetime"]).normalize()
        rain = daily_rain(ev["Latitude"], ev["Longitude"], event_day.year)
        row = {"slide": ev["Slide_Name"], "date": event_day.date(), "month": event_day.month}
        pool = rain.index[
            rain.index.month.isin(MONSOON)
            & (rain.index.year == event_day.year)
            & (abs((rain.index - event_day).days) > EXCLUDE_DAYS_AROUND_EVENT)
        ]
        for cap in caps:
            flags = alerting(rain, [d for d in caps if d <= cap], config)
            row[f"caught_{cap}"] = bool(flags.get(event_day - timedelta(days=1), False))
            ordinary[cap].append(float(flags.loc[pool].mean()))
        per_event.append(row)
        time.sleep(0.25)
    result = pd.DataFrame(per_event)
    monsoon = result["month"].isin(MONSOON)

    table = pd.DataFrame({
        "longest_window_days": caps,
        "caught_all_68": [int(result[f"caught_{c}"].sum()) for c in caps],
        "caught_monsoon_slides": [int(result.loc[monsoon, f"caught_{c}"].sum()) for c in caps],
        "ordinary_monsoon_days_alerting_%": [round(100 * sum(ordinary[c]) / len(ordinary[c]), 1) for c in caps],
    })
    print(f"slides: {len(result)} total, {int(monsoon.sum())} in Jun-Sep\n")
    print(table.to_string(index=False))

    short, full = f"caught_{caps[2]}", f"caught_{caps[-1]}"  # up to 5 days vs every window
    only_long = result[result[full] & ~result[short]]
    print(f"\ncaught ONLY thanks to windows longer than {caps[2]} days: {len(only_long)} of {len(result)}")
    print(f"caught by neither: {int((~result[full]).sum())} of {len(result)}")

    out = DEFAULT_CONFIG.paths.case_study_csv.parent / "rule_comparison.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(out, index=False)
    print(f"\nper-slide results saved -> {out}")
    return table


if __name__ == "__main__":
    run()
