"""
Completes RUSLE: computes R (rainfall erosivity), the last missing factor,
and produces the full annual soil-loss estimate A = R x K x LS x C x P.

There's no separate rainfall-erosivity dataset to download -- R has to be
computed from actual rainfall records. Open-Meteo's historical archive API
(already the team's confirmed working rainfall source, per the onboarding
doc's Section 8 -- IMD/ENVIS/SSDMA all failed) supports batched
multi-location queries, so this samples a grid of points across Sikkim at
roughly ERA5's native ~10km resolution, pulls 10 years of daily
precipitation per point, and derives R via the Modified Fournier Index.

Method (standard when only monthly/daily totals are available, not
sub-hourly intensity -- which nobody has for Sikkim):
  MFI = sum(P_month^2) / P_annual   (Modified Fournier Index)
  R = 4.17 * MFI - 152              (Arnoldus, 1980, MJ*mm/(ha*h*yr))
This is a literature-standard formula, widely used in exactly this
data-scarce situation across South/Southeast Asian RUSLE studies -- but
like the team's Harilal et al. rainfall threshold, it's a real citable
source, not something invented here. Verify the exact coefficients against
the primary text before quoting them to judges.

Point R-factor values are interpolated onto the DEM's grid, then combined
with the already-computed K, LS, C (scripts/10, /11) and P=1.0 to produce
the actual RUSLE output.

Also derives mean_annual_rainfall_mm (the raw climatology, not just the
derived erosivity) since Role B's handoff spec requires it as its own
column -- interpolated onto the DEM grid the same way as R.

Outputs:
  data/raw/rainfall_erosivity_points.csv       (per-point R + rainfall, for transparency)
  data/processed/rusle_r_factor.tif            (interpolated R-factor)
  data/processed/mean_annual_rainfall_mm.tif   (interpolated rainfall climatology)
  data/processed/rusle_soil_loss_annual.tif    (A = R x K x LS x C x P, t/ha/yr)

Caches each batch's raw daily-precip response to data/interim/rainfall_cache/
so re-running this (e.g. to add a field) doesn't need to re-hit Open-Meteo's
rate-limited archive API for data already fetched once.
"""
import hashlib
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.warp import Resampling
from scipy.interpolate import griddata
from shapely.geometry import shape, Point

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
CACHE_DIR = ROOT / "data" / "interim" / "rainfall_cache"
DEM_PATH = PROCESSED / "dem_sikkim_utm45n.tif"
NODATA = -9999.0

GRID_SPACING_DEG = 0.09  # ~10km, matches ERA5's native resolution -- no point oversampling
START_DATE, END_DATE = "2014-01-01", "2023-12-31"  # 10-year climatology
BATCH_SIZE = 12  # smaller batches after hitting 429s at 25 points x 10yrs back-to-back
BATCH_PAUSE_SECONDS = 8
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def build_sample_grid():
    with open(RAW / "sikkim_boundary.geojson") as f:
        gj = json.load(f)
    boundary = shape(gj["features"][0]["geometry"])
    minx, miny, maxx, maxy = boundary.bounds
    pad = 0.1  # so edge/corner interpolation has real data nearby, not just extrapolation
    lats = np.arange(miny - pad, maxy + pad, GRID_SPACING_DEG)
    lons = np.arange(minx - pad, maxx + pad, GRID_SPACING_DEG)
    points = [(round(float(la), 4), round(float(lo), 4)) for la in lats for lo in lons]
    return points


def fetch_batch(points):
    lats = ",".join(str(p[0]) for p in points)
    lons = ",".join(str(p[1]) for p in points)
    params = {
        "latitude": lats, "longitude": lons,
        "start_date": START_DATE, "end_date": END_DATE,
        "daily": "precipitation_sum", "timezone": "Asia/Kolkata",
    }
    url = ARCHIVE_URL + "?" + urllib.parse.urlencode(params)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_key = hashlib.sha1(url.encode()).hexdigest()[:16]
    cache_path = CACHE_DIR / f"{cache_key}.json"
    if cache_path.exists():
        with open(cache_path) as f:
            return json.load(f), True

    backoffs = [15, 45, 90, 180]
    for attempt in range(len(backoffs) + 1):
        try:
            with urllib.request.urlopen(url, timeout=90) as resp:
                data = json.load(resp)
            with open(cache_path, "w") as f:
                json.dump(data, f)
            return data, False
        except Exception as e:
            print(f"    batch attempt {attempt+1} failed: {e}")
            if attempt < len(backoffs):
                print(f"    backing off {backoffs[attempt]}s...")
                time.sleep(backoffs[attempt])
    raise RuntimeError("batch fetch failed after all retries")


def monthly_r_factor(daily_dates, daily_precip):
    """MFI -> R (Arnoldus 1980), from 10 years of daily precip."""
    from collections import defaultdict
    monthly_by_year = defaultdict(lambda: defaultdict(float))
    for date_str, p in zip(daily_dates, daily_precip):
        if p is None:
            continue
        year, month = date_str[:4], date_str[5:7]
        monthly_by_year[year][month] += p

    n_years = len(monthly_by_year)
    monthly_means = []
    for month in [f"{m:02d}" for m in range(1, 13)]:
        vals = [monthly_by_year[y][month] for y in monthly_by_year if month in monthly_by_year[y]]
        monthly_means.append(sum(vals) / len(vals) if vals else 0.0)

    annual_mean = sum(monthly_means)
    if annual_mean <= 0:
        return None, None, None
    mfi = sum(p ** 2 for p in monthly_means) / annual_mean
    r = 4.17 * mfi - 152
    r = max(r, 0.0)  # R-factor isn't physically negative
    return mfi, r, annual_mean


def main():
    points = build_sample_grid()
    print(f"Sample grid: {len(points)} points at ~{GRID_SPACING_DEG}deg spacing")

    results = []
    skipped_batches = 0
    for i in range(0, len(points), BATCH_SIZE):
        batch = points[i:i + BATCH_SIZE]
        print(f"Fetching batch {i//BATCH_SIZE + 1}/{(len(points)-1)//BATCH_SIZE + 1} ({len(batch)} points)...")
        try:
            data, was_cached = fetch_batch(batch)
        except RuntimeError as e:
            print(f"  SKIPPING this batch after exhausting retries: {e}")
            skipped_batches += 1
            continue
        if was_cached:
            print("  (from cache)")
        for (lat, lon), entry in zip(batch, data):
            times = entry["daily"]["time"]
            precip = entry["daily"]["precipitation_sum"]
            mfi, r, annual_rain = monthly_r_factor(times, precip)
            if r is not None:
                results.append({
                    "lat": lat, "lon": lon, "mfi": round(mfi, 2), "r_factor": round(r, 2),
                    "mean_annual_rainfall_mm": round(annual_rain, 1),
                })
        if i + BATCH_SIZE < len(points) and not was_cached:
            time.sleep(BATCH_PAUSE_SECONDS)

    print(f"\nComputed R-factor at {len(results)} points"
          + (f" ({skipped_batches} batch(es) skipped after Open-Meteo rate-limited them past all retries)"
             if skipped_batches else ""))
    out_csv = RAW / "rainfall_erosivity_points.csv"
    with open(out_csv, "w") as f:
        f.write("lat,lon,mfi,r_factor,mean_annual_rainfall_mm\n")
        for row in results:
            f.write(f"{row['lat']},{row['lon']},{row['mfi']},{row['r_factor']},{row['mean_annual_rainfall_mm']}\n")
    print(f"Wrote {out_csv}")

    r_vals = np.array([row["r_factor"] for row in results])
    print(f"  R-factor range: {r_vals.min():.1f} - {r_vals.max():.1f}, median {np.median(r_vals):.1f}")
    print("  (literature range for monsoon South Asia is roughly 2000-12000 MJ*mm/(ha*h*yr))")

    print("\nInterpolating R-factor onto the DEM grid...")
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32645", always_xy=True)
    pts_utm = np.array([to_utm.transform(row["lon"], row["lat"]) for row in results])

    with rasterio.open(DEM_PATH) as src:
        dem_meta = src.meta.copy()
        dem_arr = src.read(1)
        transform = src.transform

    rows, cols = np.meshgrid(np.arange(dem_meta["height"]), np.arange(dem_meta["width"]), indexing="ij")
    xs, ys = rasterio.transform.xy(transform, rows.ravel(), cols.ravel())
    grid_xy = np.column_stack([xs, ys])

    r_interp = griddata(pts_utm, r_vals, grid_xy, method="linear")
    r_interp_nearest = griddata(pts_utm, r_vals, grid_xy, method="nearest")
    r_interp = np.where(np.isnan(r_interp), r_interp_nearest, r_interp)  # fill edge/extrapolation gaps
    r_grid = r_interp.reshape(dem_meta["height"], dem_meta["width"])

    valid = dem_arr != NODATA
    r_out = np.where(valid, r_grid, NODATA).astype(np.float32)

    r_path = PROCESSED / "rusle_r_factor.tif"
    r_meta = dem_meta.copy()
    r_meta.update(dtype="float32", nodata=NODATA, compress="deflate")
    with rasterio.open(r_path, "w", **r_meta) as dst:
        dst.write(r_out, 1)
    print(f"Wrote {r_path}")

    print("\nInterpolating mean annual rainfall onto the DEM grid...")
    rain_vals = np.array([row["mean_annual_rainfall_mm"] for row in results])
    rain_interp = griddata(pts_utm, rain_vals, grid_xy, method="linear")
    rain_interp_nearest = griddata(pts_utm, rain_vals, grid_xy, method="nearest")
    rain_interp = np.where(np.isnan(rain_interp), rain_interp_nearest, rain_interp)
    rain_grid = rain_interp.reshape(dem_meta["height"], dem_meta["width"])
    rain_out = np.where(valid, rain_grid, NODATA).astype(np.float32)

    rain_path = PROCESSED / "mean_annual_rainfall_mm.tif"
    with rasterio.open(rain_path, "w", **r_meta) as dst:
        dst.write(rain_out, 1)
    print(f"Wrote {rain_path}")
    print(f"  range: {rain_vals.min():.0f} - {rain_vals.max():.0f} mm, median {np.median(rain_vals):.0f} mm")

    print("\nCombining full RUSLE: A = R x K x LS x C x P...")
    with rasterio.open(PROCESSED / "rusle_klcp_partial.tif") as src:
        klcp = src.read(1)
        klcp_nodata = src.nodata

    combined_valid = (klcp != klcp_nodata) & (r_out != NODATA)
    soil_loss = klcp * r_out  # P already folded into klcp from script 11
    soil_loss_out = np.where(combined_valid, soil_loss, NODATA).astype(np.float32)

    loss_path = PROCESSED / "rusle_soil_loss_annual.tif"
    loss_meta = dem_meta.copy()
    loss_meta.update(dtype="float32", nodata=NODATA, compress="deflate")
    with rasterio.open(loss_path, "w", **loss_meta) as dst:
        dst.write(soil_loss_out, 1)
    print(f"Wrote {loss_path}")

    loss_vals = soil_loss_out[combined_valid]
    print("\nSanity check -- full RUSLE annual soil loss (t/ha/yr):")
    print(f"  valid pixels: {combined_valid.sum():,}")
    print(f"  range: {loss_vals.min():.2f} - {loss_vals.max():.2f}")
    print(f"  median: {np.median(loss_vals):.2f}")
    print(f"  90th percentile: {np.percentile(loss_vals, 90):.2f}")
    print("  (published Himalayan RUSLE studies typically report low single digits under forest,")
    print("   tens to 100+ t/ha/yr on steep bare/cropped/degraded slopes)")


if __name__ == "__main__":
    main()
