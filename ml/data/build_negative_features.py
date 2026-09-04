"""
Extracts the same feature columns as data/processed/handoff_for_B.csv, but for
the negative (non-landslide) points A already generated with a road-bias-
matched method (scripts/04_generate_negative_samples.py) -- NOT a naive
buffer-only approach.

Why not naive buffer-only sampling: 97% of the real landslide points sit
within 100m of a road (a reporting artifact, not physics -- see
data/PROVENANCE.md). A's negative-sampling method corrects for this by
matching negatives to the real positives' road-distance distribution. A
plain random-point-plus-buffer approach would NOT correct for this, and the
model could trivially learn "far from a road = safe" as a fake predictor.
So: reuse A's negative point *locations* (data/raw/sikkim_negative_samples.csv),
just run them through the same raster-sampling method used for the positive
points (scripts/15_build_handoff_csv.py), to get matching feature columns.

Run from the repo root: python ml/data/build_negative_features.py
Input:  data/raw/sikkim_negative_samples.csv (lon, lat, distance_to_road_m)
        data/processed/*.tif (same rasters used for handoff_for_B.csv)
Output: data/processed/negative_features_for_B.csv, same schema as
        handoff_for_B.csv, all rows label=0.
"""

import csv
from pathlib import Path

import rasterio
from pyproj import Transformer

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW = REPO_ROOT / "data" / "raw"
PROCESSED = REPO_ROOT / "data" / "processed"
NODATA = -9999.0

# Same mapping as scripts/15_build_handoff_csv.py -- ESA WorldCover numeric
# code -> plain category name.
LANDUSE_NAMES = {
    10: "forest", 20: "shrubland", 30: "grassland", 40: "cropland",
    50: "built-up", 60: "bare/sparse vegetation", 70: "snow/ice",
    80: "water", 90: "wetland", 95: "mangroves", 100: "moss/lichen",
}

RASTERS = {
    "elevation": (PROCESSED / "dem_sikkim_utm45n.tif", NODATA),
    "slope_deg": (PROCESSED / "slope_deg.tif", NODATA),
    "aspect_deg": (PROCESSED / "aspect_deg.tif", NODATA),
    "drainage_density": (PROCESSED / "drainage_density.tif", NODATA),
    "landuse_code": (PROCESSED / "landcover_sikkim_utm45n.tif", 255),
    "mean_annual_rainfall_mm": (PROCESSED / "mean_annual_rainfall_mm.tif", NODATA),
    "distance_to_drainage": (PROCESSED / "distance_to_stream_m.tif", NODATA),
    "curvature": (PROCESSED / "curvature.tif", NODATA),
    "terrain_ruggedness": (PROCESSED / "terrain_ruggedness.tif", NODATA),
}

REQUIRED_FOR_TRAINING = ["elevation", "slope_deg", "aspect_deg", "drainage_density",
                          "landuse_code", "mean_annual_rainfall_mm"]


def load_negative_points(path=None):
    path = path or (RAW / "sikkim_negative_samples.csv")
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32645", always_xy=True)
    points = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            lon, lat = float(row["Longitude"]), float(row["Latitude"])
            x, y = to_utm.transform(lon, lat)
            points.append({
                "sample_id": f"NEG-{i:04d}",
                "lat": lat, "lon": lon, "x_utm": x, "y_utm": y,
                "label": 0,
            })
    return points


def sample_rasters(points):
    for col, (path, nodata_val) in RASTERS.items():
        with rasterio.open(path) as src:
            coords = [(p["x_utm"], p["y_utm"]) for p in points]
            for p, val in zip(points, src.sample(coords)):
                v = float(val[0])
                p[col] = None if v == nodata_val else v
    return points


def main():
    print("Loading A's road-bias-matched negative points...")
    points = load_negative_points()
    print(f"  {len(points)} points")

    print("Sampling all raster layers (same method as handoff_for_B.csv)...")
    points = sample_rasters(points)

    missing = [p for p in points if any(p[c] is None for c in REQUIRED_FOR_TRAINING)]
    if missing:
        print(f"  WARNING: {len(missing)} points missing a required field -- dropping them")
        points = [p for p in points if all(p[c] is not None for c in REQUIRED_FOR_TRAINING)]

    out_path = PROCESSED / "negative_features_for_B.csv"
    cols = ["sample_id", "lat", "lon", "elevation", "slope_deg", "aspect_deg",
            "drainage_density", "lithology", "landuse", "mean_annual_rainfall_mm", "label",
            "district", "date", "landslide_type", "area_m2",
            "curvature", "distance_to_drainage", "terrain_ruggedness"]

    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        for p in points:
            writer.writerow({
                "sample_id": p["sample_id"], "lat": round(p["lat"], 6), "lon": round(p["lon"], 6),
                "elevation": round(p["elevation"], 1), "slope_deg": round(p["slope_deg"], 2),
                "aspect_deg": round(p["aspect_deg"], 2), "drainage_density": round(p["drainage_density"], 4),
                "lithology": "",  # same genuine gap as the positive points -- not fabricated
                "landuse": LANDUSE_NAMES.get(int(p["landuse_code"]), ""),
                "mean_annual_rainfall_mm": round(p["mean_annual_rainfall_mm"], 1),
                "label": p["label"],
                "district": "", "date": "", "landslide_type": "", "area_m2": "",
                "curvature": round(p["curvature"], 6) if p["curvature"] is not None else "",
                "distance_to_drainage": round(p["distance_to_drainage"], 1) if p["distance_to_drainage"] is not None else "",
                "terrain_ruggedness": round(p["terrain_ruggedness"], 2) if p["terrain_ruggedness"] is not None else "",
            })

    print(f"Wrote {out_path} ({len(points)} rows, {len(cols)} columns)")


if __name__ == "__main__":
    main()
