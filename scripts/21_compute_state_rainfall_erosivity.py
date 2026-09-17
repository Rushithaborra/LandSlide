"""
Generalized version of scripts/13 (RUSLE R-factor + full soil-loss combine),
parameterized by state. Same method: Open-Meteo historical archive API,
10-year daily precipitation, Modified Fournier Index -> Arnoldus (1980)
R-factor, same literature-verify-before-quoting caveat as Sikkim's.

Usage: python3 scripts/21_compute_state_rainfall_erosivity.py <state_slug>

Requires scripts/18's outputs (dem_<state>.tif, rusle_k_factor_<state>.tif
resampled via rusle_ls_factor/_c_factor) to already exist.

Shares the same rate-limit-hit reality as Sikkim's run: Open-Meteo's
archive API 429s on sustained batch traffic. Uses the same cache dir
(data/interim/rainfall_cache/, keyed by request URL so it's safely shared
across states) and the same skip-after-exhausting-retries behavior rather
than crashing the whole run over one bad batch.

Outputs:
  data/raw/rainfall_erosivity_points_<state>.csv
  data/processed/rusle_r_factor_<state>.tif
  data/processed/mean_annual_rainfall_mm_<state>.tif
  data/processed/rusle_soil_loss_annual_<state>.tif
"""
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from scipy.interpolate import griddata

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ner_config import STATE_CONFIGS

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
CACHE_DIR = ROOT / "data" / "interim" / "rainfall_cache"
NODATA = -9999.0

GRID_SPACING_DEG = 0.09  # ~10km, matches ERA5 native resolution, same as Sikkim's
# Assam and Arunachal Pradesh are ~4-5x the area of the other NER states.
# At the default 0.09deg spacing that's ~270 and ~193 Open-Meteo batches
# respectively -- observed in practice at roughly 5-7 min/batch against
# this API's rate limiting, i.e. 20-30+ hours EACH just for rainfall. That's
# not a reasonable tradeoff for one of 13 feature columns. Widening the
# grid to 0.20deg for just these two states brings them to ~58 and ~42
# batches -- back in line with the other states' actual completion time --
# at the cost of coarser rainfall-erosivity spatial resolution for them
# specifically. This is a disclosed methodological choice, not a silent
# shortcut: flagged here, in the pipeline log output, and in
# docs/dataset_inventory.md.
COARSE_GRID_STATES = {"assam": 0.25, "arunachal_pradesh": 0.25}
START_DATE, END_DATE = "2014-01-01", "2023-12-31"
BATCH_SIZE = 12
BATCH_PAUSE_SECONDS = 8
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def build_sample_grid(bbox, slug, pad=0.1):
    spacing = COARSE_GRID_STATES.get(slug, GRID_SPACING_DEG)
    if slug in COARSE_GRID_STATES:
        print(f"  NOTE: using coarser {spacing}deg rainfall sample grid for {slug} "
              f"(vs. the {GRID_SPACING_DEG}deg default) -- its area would otherwise need "
              f"hundreds of rate-limited Open-Meteo batches; see this script's docstring")
    minx, miny, maxx, maxy = bbox
    lats = np.arange(miny - pad, maxy + pad, spacing)
    lons = np.arange(minx - pad, maxx + pad, spacing)
    return [(round(float(la), 4), round(float(lo), 4)) for la in lats for lo in lons]


def fetch_batch(points):
    lats = ",".join(str(p[0]) for p in points)
    lons = ",".join(str(p[1]) for p in points)
    params = {"latitude": lats, "longitude": lons, "start_date": START_DATE, "end_date": END_DATE,
              "daily": "precipitation_sum", "timezone": "Asia/Kolkata"}
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
    from collections import defaultdict
    monthly_by_year = defaultdict(lambda: defaultdict(float))
    for date_str, p in zip(daily_dates, daily_precip):
        if p is None:
            continue
        year, month = date_str[:4], date_str[5:7]
        monthly_by_year[year][month] += p
    monthly_means = []
    for month in [f"{m:02d}" for m in range(1, 13)]:
        vals = [monthly_by_year[y][month] for y in monthly_by_year if month in monthly_by_year[y]]
        monthly_means.append(sum(vals) / len(vals) if vals else 0.0)
    annual_mean = sum(monthly_means)
    if annual_mean <= 0:
        return None, None, None
    mfi = sum(p ** 2 for p in monthly_means) / annual_mean
    r = max(4.17 * mfi - 152, 0.0)
    return mfi, r, annual_mean


def run(slug):
    cfg = STATE_CONFIGS[slug]
    dem_path = PROCESSED / f"dem_{slug}.tif"
    dst_crs = cfg["dst_crs"]
    points = build_sample_grid(cfg["bbox"], slug)
    print(f"=== {cfg['display_name']} rainfall erosivity ===")
    print(f"Sample grid: {len(points)} points at ~{GRID_SPACING_DEG}deg spacing")

    results = []
    skipped = 0
    for i in range(0, len(points), BATCH_SIZE):
        batch = points[i:i + BATCH_SIZE]
        print(f"Batch {i//BATCH_SIZE + 1}/{(len(points)-1)//BATCH_SIZE + 1} ({len(batch)} pts)...")
        try:
            data, cached = fetch_batch(batch)
        except RuntimeError as e:
            print(f"  SKIPPING after exhausting retries: {e}")
            skipped += 1
            continue
        if cached:
            print("  (cached)")
        # Open-Meteo returns a bare dict (not a list) when the batch has
        # exactly one point, vs. a list of per-location dicts for 2+ --
        # crashed Arunachal Pradesh's final 1-point batch with "string
        # indices must be integers" (zip() iterated the dict's own keys).
        if isinstance(data, dict):
            data = [data]
        for (lat, lon), entry in zip(batch, data):
            mfi, r, annual = monthly_r_factor(entry["daily"]["time"], entry["daily"]["precipitation_sum"])
            if r is not None:
                results.append({"lat": lat, "lon": lon, "mfi": round(mfi, 2), "r_factor": round(r, 2),
                                 "mean_annual_rainfall_mm": round(annual, 1)})
        if i + BATCH_SIZE < len(points) and not cached:
            time.sleep(BATCH_PAUSE_SECONDS)

    print(f"\nComputed R-factor at {len(results)}/{len(points)} points ({skipped} batches skipped)")
    out_csv = RAW / f"rainfall_erosivity_points_{slug}.csv"
    with open(out_csv, "w") as f:
        f.write("lat,lon,mfi,r_factor,mean_annual_rainfall_mm\n")
        for row in results:
            f.write(f"{row['lat']},{row['lon']},{row['mfi']},{row['r_factor']},{row['mean_annual_rainfall_mm']}\n")
    print(f"Wrote {out_csv}")

    r_vals = np.array([r["r_factor"] for r in results])
    print(f"  R-factor range: {r_vals.min():.1f} - {r_vals.max():.1f}, median {np.median(r_vals):.1f}")

    to_utm = Transformer.from_crs("EPSG:4326", dst_crs, always_xy=True)
    pts_utm = np.array([to_utm.transform(r["lon"], r["lat"]) for r in results])

    with rasterio.open(dem_path) as src:
        dem_meta = src.meta.copy()
        dem_arr = src.read(1)
        transform = src.transform
    height, width = dem_meta["height"], dem_meta["width"]
    valid = dem_arr != NODATA

    # A single-shot meshgrid + griddata call over the whole raster needs
    # several arrays sized height*width at once (Assam: 14982x22441 =
    # ~336M cells) -- that's what silently SIGKILLed Assam's run on a 16GB
    # machine (no Python traceback, just an OS-level OOM kill). Process
    # row-chunks instead, and build each interpolator ONCE (not per chunk,
    # which would rebuild the expensive Delaunay triangulation every time)
    # via the object form of griddata's two methods.
    ROW_CHUNK = 500
    from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator

    def interp_and_write(vals, out_name):
        linear_interp = LinearNDInterpolator(pts_utm, vals)
        nearest_interp = NearestNDInterpolator(pts_utm, vals)
        out = np.full((height, width), NODATA, dtype=np.float32)
        for row0 in range(0, height, ROW_CHUNK):
            row1 = min(row0 + ROW_CHUNK, height)
            rows, cols = np.meshgrid(np.arange(row0, row1), np.arange(width), indexing="ij")
            xs, ys = rasterio.transform.xy(transform, rows.ravel(), cols.ravel())
            chunk_xy = np.column_stack([xs, ys])
            chunk_interp = linear_interp(chunk_xy)
            nan_mask = np.isnan(chunk_interp)
            if nan_mask.any():
                chunk_interp[nan_mask] = nearest_interp(chunk_xy[nan_mask])
            chunk_grid = chunk_interp.reshape(row1 - row0, width)
            chunk_valid = valid[row0:row1, :]
            out[row0:row1, :] = np.where(chunk_valid, chunk_grid, NODATA).astype(np.float32)
        out_meta = dem_meta.copy()
        out_meta.update(dtype="float32", nodata=NODATA, compress="deflate")
        path = PROCESSED / out_name
        with rasterio.open(path, "w", **out_meta) as dst:
            dst.write(out, 1)
        print(f"Wrote {path}")
        return out

    print("\nInterpolating R-factor onto DEM grid...")
    r_out = interp_and_write(r_vals, f"rusle_r_factor_{slug}.tif")
    print("Interpolating mean annual rainfall onto DEM grid...")
    rain_vals = np.array([r["mean_annual_rainfall_mm"] for r in results])
    interp_and_write(rain_vals, f"mean_annual_rainfall_mm_{slug}.tif")

    print("\nCombining full RUSLE: need K x LS x C from script 18's outputs...")
    with rasterio.open(PROCESSED / f"rusle_k_factor_{slug}.tif") as src:
        k = src.read(1)
        k_nodata = src.nodata
    with rasterio.open(PROCESSED / f"rusle_ls_factor_{slug}.tif") as src:
        ls = src.read(1)
    with rasterio.open(PROCESSED / f"rusle_c_factor_{slug}.tif") as src:
        c = src.read(1)

    # K-factor was built at SoilGrids' own reprojected grid, not necessarily
    # the DEM's exact grid -- resample onto the DEM grid before array math,
    # same fix documented for Sikkim (grid-misalignment bug in script 11).
    if k.shape != dem_arr.shape:
        from rasterio.warp import reproject, Resampling
        with rasterio.open(PROCESSED / f"rusle_k_factor_{slug}.tif") as src:
            k_regrid = np.full(dem_arr.shape, k_nodata, dtype=src.dtypes[0])
            reproject(source=rasterio.band(src, 1), destination=k_regrid,
                      src_transform=src.transform, src_crs=src.crs, src_nodata=k_nodata,
                      dst_transform=transform, dst_crs=dem_meta["crs"], dst_nodata=k_nodata,
                      resampling=Resampling.bilinear)
        k = k_regrid

    combined_valid = (k != k_nodata) & (ls != NODATA) & (c != NODATA) & (r_out != NODATA)
    soil_loss = k * ls * c * r_out
    soil_loss_out = np.where(combined_valid, soil_loss, NODATA).astype(np.float32)
    loss_meta = dem_meta.copy()
    loss_meta.update(dtype="float32", nodata=NODATA, compress="deflate")
    loss_path = PROCESSED / f"rusle_soil_loss_annual_{slug}.tif"
    with rasterio.open(loss_path, "w", **loss_meta) as dst:
        dst.write(soil_loss_out, 1)
    print(f"Wrote {loss_path}")
    loss_vals = soil_loss_out[combined_valid]
    if loss_vals.size:
        print(f"  soil loss range: {loss_vals.min():.2f} - {loss_vals.max():.2f}, median {np.median(loss_vals):.2f} t/ha/yr")


if __name__ == "__main__":
    run(sys.argv[1])
