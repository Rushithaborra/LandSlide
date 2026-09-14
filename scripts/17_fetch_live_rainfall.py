"""
Live rainfall feed for early-warning use (Feature 2), as distinct from
scripts/13's *historical* 10-year climatology (which feeds the RUSLE
R-factor, a static erosion estimate -- not something that should ever be
"live").

Source: Open-Meteo's Forecast API (api.open-meteo.com/v1/forecast) -- same
provider as scripts/13's archive API, same no-key/no-signup access, but the
live/current + short-range-forecast endpoint instead of the historical
archive endpoint. Confirmed working 2026-09-13: returns `current.precipitation`
(mm in the last hour) plus hourly precipitation for the next 7 days.

This is one script, parameterized by STATE_POINTS below -- not a
per-state copy. Each state is represented by 1-3 towns/cities sitting in
its known landslide-prone terrain (state capital + any other city named in
literature thresholds), not a dense grid -- a live rainfall check doesn't
need RUSLE's spatial-interpolation precision, it needs a handful of
monitoring points a dashboard can poll on a schedule.

Rainfall intensity-duration (ID) thresholds: only attached where a real,
citable published threshold exists for that specific location. Assam
(Guwahati) has one -- see ASSAM_ID_THRESHOLD below; every other state is
left with threshold=None rather than borrowing Assam's or Sikkim's number,
per this repo's own honesty standard (see data/PROVENANCE.md).

Output: data/raw/live_rainfall_snapshot.csv -- one row per monitoring
point, timestamped at fetch time. This is a SNAPSHOT, not a historical
record: re-run this script (e.g. on a cron / dashboard backend schedule)
to get current conditions at call time. It does not accumulate rows across
runs.
"""
import csv
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# One representative monitoring point per state (state capital, or the
# specific city a literature threshold was derived for). Not a substitute
# for per-landslide-point coverage -- see the note in main() about scaling
# this up using each state's own gsi_<state>_landslides.csv centroid once
# Step 2's boundary/DEM work exists.
STATE_POINTS = {
    "Sikkim": ("Gangtok", 27.3389, 88.6065),
    "Assam": ("Guwahati", 26.1445, 91.7362),
    "Arunachal Pradesh": ("Itanagar", 27.0844, 93.6053),
    "Manipur": ("Imphal", 24.8170, 93.9368),
    "Meghalaya": ("Shillong", 25.5788, 91.8933),
    "Mizoram": ("Aizawl", 23.7271, 92.7176),
    "Nagaland": ("Kohima", 25.6751, 94.1086),
    "Tripura": ("Agartala", 23.8315, 91.2868),
}

# Real, citable published ID threshold. NOT independently verified against
# the primary PDF in this session -- same "verify before quoting to judges"
# caveat this repo already applies to the RUSLE C-factor / Arnoldus R-factor
# (see scripts/13's docstring). Every other state is intentionally left
# without an entry: no equivalent published threshold was found for them in
# a bounded literature search, and borrowing this one would misrepresent a
# Guwahati-specific empirical fit as if it applied elsewhere.
#
# Intensity (mm/hr) = a * Duration_hours^b
# Source: "Susceptibility mapping and estimation of rainfall threshold using
# space based input for assessment of landslide hazard in Guwahati city in
# North East India", ISPRS Archives XL-8/15 (2014), derived from 19 mapped
# debris-slide incidents.
ASSAM_ID_THRESHOLD = {
    "location": "Guwahati",
    "a": 5.9,
    "b": -0.479,
    "source": "ISPRS Archives XL-8/15 (2014), Guwahati debris-slide ID threshold, n=19 events",
    "verified_against_primary_text": False,
}


def fetch_live(lat, lon):
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "precipitation,rain,temperature_2m",
        "hourly": "precipitation,precipitation_probability",
        "daily": "precipitation_sum",
        "forecast_days": 7,
        "timezone": "Asia/Kolkata",
    }
    url = FORECAST_URL + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.load(resp)


def check_assam_threshold(data):
    """Compare Guwahati's current 1hr rainfall against the ID threshold at
    duration=1hr. This is illustrative, not a full antecedent-rainfall
    early-warning model -- real ID-threshold monitoring needs the ongoing
    event's cumulative duration, which a single snapshot doesn't have."""
    current_precip_mm = data["current"]["precipitation"]
    a, b = ASSAM_ID_THRESHOLD["a"], ASSAM_ID_THRESHOLD["b"]
    threshold_intensity_1hr = a * (1.0 ** b)
    exceeds = current_precip_mm > threshold_intensity_1hr
    return current_precip_mm, threshold_intensity_1hr, exceeds


def main():
    fetched_at = datetime.now(timezone.utc).isoformat()
    rows = []
    print(f"Fetching live rainfall snapshot at {fetched_at}...\n")
    for state, (city, lat, lon) in STATE_POINTS.items():
        try:
            data = fetch_live(lat, lon)
        except Exception as e:
            print(f"{state} ({city}): FETCH FAILED -- {e}")
            continue
        current_precip = data["current"]["precipitation"]
        current_rain = data["current"]["rain"]
        next_24h_sum = sum(data["hourly"]["precipitation"][:24])
        print(f"{state:<20} {city:<10} current: {current_precip:.1f} mm (last hr) | next 24h forecast: {next_24h_sum:.1f} mm")

        threshold_note = ""
        if state == "Assam":
            intensity, threshold, exceeds = check_assam_threshold(data)
            threshold_note = f"{'EXCEEDS' if exceeds else 'below'} Guwahati ID threshold ({threshold:.2f} mm/hr @ 1hr duration)"
            print(f"  -> {threshold_note} [{ASSAM_ID_THRESHOLD['source']}, unverified against primary text]")

        rows.append({
            "state": state, "city": city, "lat": lat, "lon": lon,
            "fetched_at_utc": fetched_at,
            "current_precip_mm": current_precip,
            "current_rain_mm": current_rain,
            "next_24h_forecast_mm": round(next_24h_sum, 1),
            "id_threshold_check": threshold_note,
        })

    out_path = RAW / "live_rainfall_snapshot.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {out_path} ({len(rows)} monitoring points)")
    print("\nThis is a snapshot at fetch time, not historical data -- re-run on")
    print("a schedule (dashboard backend cron, etc.) for live monitoring.")
    print("Only Assam has a published ID threshold attached; every other")
    print("state's current/forecast rainfall is reported without a pass/fail")
    print("judgment because no equivalent citable threshold was found for it.")


if __name__ == "__main__":
    main()
