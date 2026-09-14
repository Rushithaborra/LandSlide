"""
Generalized version of scripts/05 (assemble training table) + the
land-cover/road-proximity bias audit from docs/duplicate_and_bias_audit.md's
method (recomputed per state, not copied from Sikkim's numbers), parameterized
by state.

Usage: python3 scripts/20_build_state_training_dataset.py <state_slug>

Requires scripts/18 (terrain/landcover/soil), scripts/19 (roads/negatives)
and scripts/21 (rainfall erosivity) to have already produced this state's
rasters/points.

Output: data/processed/training_dataset_<state>.csv
Same 13 columns as Sikkim's data/processed/training_table.csv:
  lon, lat, elevation_m, slope_deg, aspect_deg, distance_to_stream_m,
  landcover_class, soil_erodibility_k, rusle_ls_factor, rusle_c_factor,
  rainfall_erosivity_r, soil_loss_tha_yr, label
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from shapely.strtree import STRtree
from shapely.geometry import LineString, Point

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ner_config import STATE_CONFIGS

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
NODATA = -9999.0

CLASS_NAMES = {
    10: "Tree cover", 20: "Shrubland", 30: "Grassland", 40: "Cropland",
    50: "Built-up", 60: "Bare/sparse vegetation", 70: "Snow/ice",
    80: "Water bodies", 90: "Wetland", 95: "Mangroves", 100: "Moss/lichen",
}


def run(slug):
    cfg = STATE_CONFIGS[slug]
    dst_crs = cfg["dst_crs"]
    to_utm = Transformer.from_crs("EPSG:4326", dst_crs, always_xy=True)
    print(f"=== {cfg['display_name']} training dataset assembly ===")

    points = []
    with open(RAW / f"gsi_{slug}_landslides.csv") as f:
        for row in csv.DictReader(f):
            lon, lat = float(row["Longitude"]), float(row["Latitude"])
            points.append({"lon": lon, "lat": lat, "label": 1})
    n_pos = len(points)

    with open(RAW / f"{slug}_negative_samples.csv") as f:
        for row in csv.DictReader(f):
            points.append({"lon": float(row["Longitude"]), "lat": float(row["Latitude"]), "label": 0})
    n_neg = len(points) - n_pos
    print(f"  {n_pos} positive, {n_neg} negative, {len(points)} total")

    for p in points:
        p["x_utm"], p["y_utm"] = to_utm.transform(p["lon"], p["lat"])

    rasters = {
        "elevation_m": (PROCESSED / f"dem_{slug}.tif", NODATA),
        "slope_deg": (PROCESSED / f"slope_deg_{slug}.tif", NODATA),
        "aspect_deg": (PROCESSED / f"aspect_deg_{slug}.tif", NODATA),
        "distance_to_stream_m": (PROCESSED / f"distance_to_stream_m_{slug}.tif", NODATA),
        "landcover_class": (PROCESSED / f"landcover_{slug}.tif", 255),
        "soil_erodibility_k": (PROCESSED / f"rusle_k_factor_{slug}.tif", NODATA),
        "rusle_ls_factor": (PROCESSED / f"rusle_ls_factor_{slug}.tif", NODATA),
        "rusle_c_factor": (PROCESSED / f"rusle_c_factor_{slug}.tif", NODATA),
        "rainfall_erosivity_r": (PROCESSED / f"rusle_r_factor_{slug}.tif", NODATA),
        "soil_loss_tha_yr": (PROCESSED / f"rusle_soil_loss_annual_{slug}.tif", NODATA),
    }
    print("Sampling rasters at each point...")
    for col, (path, nodata_val) in rasters.items():
        with rasterio.open(path) as src:
            coords = [(p["x_utm"], p["y_utm"]) for p in points]
            for p, val in zip(points, src.sample(coords)):
                v = float(val[0])
                if v == nodata_val or (nodata_val == NODATA and np.isnan(v)):
                    p[col] = None
                elif col == "landcover_class":
                    p[col] = int(v)
                else:
                    p[col] = round(v, 3)

    raster_cols = list(rasters.keys())
    missing = [p for p in points if any(p[c] is None for c in raster_cols)]
    if missing:
        print(f"  WARNING: {len(missing)}/{len(points)} points had nodata in >=1 raster (likely fell on a "
              f"raster-coverage gap, e.g. a DEM tile that failed to download) -- dropping them, not imputing")
        points = [p for p in points if all(p[c] is not None for c in raster_cols)]

    cols = ["lon", "lat", "elevation_m", "slope_deg", "aspect_deg", "distance_to_stream_m", "landcover_class",
            "soil_erodibility_k", "rusle_ls_factor", "rusle_c_factor", "rainfall_erosivity_r",
            "soil_loss_tha_yr", "label"]
    out_path = PROCESSED / f"training_dataset_{slug}.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        for p in points:
            writer.writerow({c: p[c] for c in cols})
    print(f"Wrote {out_path} ({len(points)} rows, {len(cols)} columns)")

    # --- Bias check: recomputed for THIS state, not copied from Sikkim ---
    print(f"\n=== Bias audit for {cfg['display_name']} (own numbers, not Sikkim's) ===")
    pos_pts = [p for p in points if p["label"] == 1]
    neg_pts = [p for p in points if p["label"] == 0]

    lc_pos = [p["landcover_class"] for p in pos_pts]
    lc_neg = [p["landcover_class"] for p in neg_pts]
    builtup_pos = 100 * sum(1 for c in lc_pos if c == 50) / len(lc_pos) if lc_pos else 0
    builtup_neg = 100 * sum(1 for c in lc_neg if c == 50) / len(lc_neg) if lc_neg else 0
    print(f"  Built-up land cover: positives {builtup_pos:.1f}% vs negatives {builtup_neg:.1f}%"
          f" {'(possible reporting-proximity artifact, same pattern flagged for Sikkim)' if builtup_pos > builtup_neg * 1.5 else ''}")

    dist_pos = [p["distance_to_stream_m"] for p in pos_pts]
    dist_neg = [p["distance_to_stream_m"] for p in neg_pts]
    print(f"  Distance to stream: positives median {np.median(dist_pos):.1f}m vs negatives median {np.median(dist_neg):.1f}m")

    with open(RAW / f"{slug}_roads.geojson") as f:
        roads_gj = json.load(f)
    road_lines = [LineString([to_utm.transform(lon, lat) for lon, lat in feat["geometry"]["coordinates"]])
                  for feat in roads_gj["features"]]
    tree = STRtree(road_lines)
    road_dists = []
    for p in pos_pts:
        pt = Point(p["x_utm"], p["y_utm"])
        idx = tree.nearest(pt)
        road_dists.append(pt.distance(road_lines[idx]))
    road_dists = np.array(road_dists)
    pct_100m = 100 * np.sum(road_dists <= 100) / len(road_dists)
    print(f"  Road-proximity bias (positives only): {pct_100m:.1f}% within 100m of a road "
          f"(median {np.median(road_dists):.1f}m) -- this state's own measurement, not assumed from Sikkim's 97.0%")

    print("\nClass distribution (% of points, positives+negatives combined):")
    from collections import Counter
    all_lc = Counter(p["landcover_class"] for p in points)
    total = sum(all_lc.values())
    for code, n in sorted(all_lc.items()):
        print(f"  {code:>3} {CLASS_NAMES.get(code, f'class {code}'):<25} {100*n/total:5.1f}%")


if __name__ == "__main__":
    run(sys.argv[1])
