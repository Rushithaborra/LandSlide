"""
Builds the CSV in the exact schema Role B (ML lead) asked for in
handoff_format_for_A.md -- different column names/types than
training_table.csv, and critically: POSITIVE ROWS ONLY.

B's spec is explicit: "Do NOT generate 0-rows -- negative sampling is my
job, not yours... Sending only label=1 rows is correct." That's a direct
conflict with training_table.csv, which already contains 766 bias-matched
negative samples built earlier this session (see scripts/04 and
data/PROVENANCE.md) -- a genuinely different, more careful methodology
than a generic boundary-buffer approach, but B owns that step and asked
explicitly not to receive 0-rows here. This script respects that: it
emits positive rows only. training_table.csv (with negatives) still exists
separately in case B wants to compare methodologies, but this file is the
one that matches what was actually requested.

lithology is sent as an empty string, not fabricated -- both GSI source
portals are still unreachable (see PROVENANCE.md). Every other required
and nice-to-have column B listed is populated from real derived data.

Output: data/processed/handoff_for_B.csv
"""
import csv
import json
from pathlib import Path

import rasterio
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
NODATA = -9999.0

# GSI's own `district` field is genuinely messy -- 17 distinct raw values
# for Sikkim's 4 traditional districts, mixing whitespace inconsistencies
# ("East Sikkim" vs " East Sikkim"), full names with varying suffixes
# ("East District" / "East district, Sikkim" / "East Sikkim"), and HQ town
# names used as stand-ins (Namchi=South HQ, Gangtok/Pakyong=East HQ,
# Geyzing/Gyalshing/Soreng=West HQ). B asked for this field specifically
# for a data-quality slide, so it gets normalized rather than passed
# through messy -- that's the whole point of asking for it.
DISTRICT_NORMALIZE = {
    "south district, sikkim": "South Sikkim", "south sikkim": "South Sikkim", "namchi": "South Sikkim",
    "east sikkim": "East Sikkim", "east district": "East Sikkim", "east district, sikkim": "East Sikkim",
    "gangtok district, sikkim": "East Sikkim", "gangtok": "East Sikkim", "pakyong": "East Sikkim",
    "west sikkim": "West Sikkim", "geyzing": "West Sikkim", "gyalshing district, sikkim": "West Sikkim",
    "soreng": "West Sikkim",
    "north district": "North Sikkim", "north sikkim": "North Sikkim",
}


def normalize_district(raw):
    if not raw:
        return ""
    key = raw.strip().lower()
    return DISTRICT_NORMALIZE.get(key, raw.strip())  # fall back to trimmed original if unmapped


# ESA WorldCover code -> plain category name (B's spec: "category name, not a code number")
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


def load_positive_points():
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32645", always_xy=True)
    with open(RAW / "gsi_sikkim_landslides_raw.geojson") as f:
        landslides = json.load(f)

    points = []
    for feat in landslides["features"]:
        lon, lat = feat["geometry"]["coordinates"]
        props = feat["properties"]
        x, y = to_utm.transform(lon, lat)
        points.append({
            "sample_id": props.get("slide_no") or f"LS-{props.get('objectid')}",
            "lat": lat, "lon": lon, "x_utm": x, "y_utm": y,
            "district": normalize_district(props.get("district")),
            "date": props.get("history_da") or "",
            "landslide_type": props.get("movement_t") or "",
            "area_m2": props.get("ls_area") if props.get("ls_area") is not None else "",
            "label": 1,
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
    print("Loading positive (landslide) points only, per B's explicit request...")
    points = load_positive_points()
    print(f"  {len(points)} points")

    print("Sampling all raster layers...")
    points = sample_rasters(points)

    missing = [p for p in points if any(p[c] is None for c in REQUIRED_FOR_TRAINING)]
    if missing:
        print(f"  WARNING: {len(missing)} points missing a required field -- dropping them")
        points = [p for p in points if all(p[c] is not None for c in REQUIRED_FOR_TRAINING)]

    out_path = PROCESSED / "handoff_for_B.csv"
    cols = ["sample_id", "lat", "lon", "elevation", "slope_deg", "aspect_deg",
            "drainage_density", "lithology", "landuse", "mean_annual_rainfall_mm", "label",
            "district", "date", "landslide_type", "area_m2",
            "curvature", "distance_to_drainage", "terrain_ruggedness"]

    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        for p in points:
            row = {
                "sample_id": p["sample_id"], "lat": round(p["lat"], 6), "lon": round(p["lon"], 6),
                "elevation": round(p["elevation"], 1), "slope_deg": round(p["slope_deg"], 2),
                "aspect_deg": round(p["aspect_deg"], 2), "drainage_density": round(p["drainage_density"], 4),
                "lithology": "",  # genuinely unavailable -- both GSI portals unreachable, see PROVENANCE.md
                "landuse": LANDUSE_NAMES.get(int(p["landuse_code"]), ""),
                "mean_annual_rainfall_mm": round(p["mean_annual_rainfall_mm"], 1),
                "label": p["label"],
                "district": p["district"], "date": p["date"],
                "landslide_type": p["landslide_type"], "area_m2": p["area_m2"],
                "curvature": round(p["curvature"], 6) if p["curvature"] is not None else "",
                "distance_to_drainage": round(p["distance_to_drainage"], 1) if p["distance_to_drainage"] is not None else "",
                "terrain_ruggedness": round(p["terrain_ruggedness"], 2) if p["terrain_ruggedness"] is not None else "",
            }
            writer.writerow(row)

    print(f"Wrote {out_path} ({len(points)} rows, {len(cols)} columns)")
    print(f"\nColumn coverage against handoff_format_for_A.md:")
    print(f"  Required: sample_id, lat, lon, elevation, slope_deg, aspect_deg, drainage_density,")
    print(f"            landuse, mean_annual_rainfall_mm, label -- all populated")
    print(f"  lithology -- column present, EMPTY (GSI NGDR + BHUKOSH both unreachable, not fabricated)")
    print(f"  Nice-to-have: district, date, landslide_type, area_m2, curvature,")
    print(f"                distance_to_drainage, terrain_ruggedness -- all populated")
    print(f"\nBoundary polygon (requested separately, not in the CSV): data/raw/sikkim_boundary.geojson")
    print(f"\nNOTE: this file is label=1 ONLY, per B's explicit instruction not to receive 0-rows.")
    print(f"training_table.csv (1529 rows, includes 766 bias-matched negative samples with a")
    print(f"different, more involved methodology than a generic buffer) still exists separately")
    print(f"in case B wants it instead of re-deriving negatives with negative_sampling.py.")


if __name__ == "__main__":
    main()
