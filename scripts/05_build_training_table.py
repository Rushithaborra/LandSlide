"""
Day 2-3 (Role A - Data/GIS): the actual handoff deliverable to the ML lead (B).

Joins positive (landslide) and negative (generated) points against every
terrain raster produced so far and writes one flat CSV: one row per point,
features + label. Re-run this any time a new raster lands -- downstream
just re-joins on lon/lat.

Output: data/processed/training_table.csv
Columns: lon, lat, elevation_m, slope_deg, aspect_deg, distance_to_stream_m,
         landcover_class, soil_erodibility_k, rusle_ls_factor,
         rusle_c_factor, rainfall_erosivity_r, soil_loss_tha_yr, label
  label: 1 = landslide, 0 = not
  landcover_class: ESA WorldCover code (10=Tree cover, 20=Shrubland,
    30=Grassland, 40=Cropland, 50=Built-up, 60=Bare/sparse, 70=Snow/ice,
    80=Water, 90=Wetland, 95=Mangroves, 100=Moss/lichen)
  soil_erodibility_k / rusle_ls_factor / rusle_c_factor / rainfall_erosivity_r:
    the individual RUSLE factors (scripts/10, /11, /13) at this point
  soil_loss_tha_yr: full RUSLE annual soil loss estimate (K*LS*C*P*R),
    t/ha/yr -- the erosion-model output, included here so the same point
    set supports both susceptibility and erosion analysis
Lithology is NOT in this table -- both GSI source portals (NGDR, BHUKOSH)
are unreachable; see data/PROVENANCE.md.
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


def load_points():
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32645", always_xy=True)
    points = []

    with open(RAW / "gsi_sikkim_landslides_raw.geojson") as f:
        landslides = json.load(f)
    for feat in landslides["features"]:
        lon, lat = feat["geometry"]["coordinates"]
        points.append({"lon": lon, "lat": lat, "label": 1})

    with open(RAW / "sikkim_negative_samples.csv") as f:
        reader = csv.DictReader(f)
        for row in reader:
            points.append({"lon": float(row["Longitude"]), "lat": float(row["Latitude"]), "label": 0})

    for p in points:
        p["x_utm"], p["y_utm"] = to_utm.transform(p["lon"], p["lat"])

    return points


def sample_rasters(points):
    rasters = {
        "elevation_m": (PROCESSED / "dem_sikkim_utm45n.tif", NODATA),
        "slope_deg": (PROCESSED / "slope_deg.tif", NODATA),
        "aspect_deg": (PROCESSED / "aspect_deg.tif", NODATA),
        "distance_to_stream_m": (PROCESSED / "distance_to_stream_m.tif", NODATA),
        "landcover_class": (PROCESSED / "landcover_sikkim_utm45n.tif", 255),
        "soil_erodibility_k": (PROCESSED / "rusle_k_factor.tif", NODATA),
        "rusle_ls_factor": (PROCESSED / "rusle_ls_factor.tif", NODATA),
        "rusle_c_factor": (PROCESSED / "rusle_c_factor.tif", NODATA),
        "rainfall_erosivity_r": (PROCESSED / "rusle_r_factor.tif", NODATA),
        "soil_loss_tha_yr": (PROCESSED / "rusle_soil_loss_annual.tif", NODATA),
    }
    for col, (path, nodata_val) in rasters.items():
        with rasterio.open(path) as src:
            coords = [(p["x_utm"], p["y_utm"]) for p in points]
            for p, val in zip(points, src.sample(coords)):
                v = float(val[0])
                if v == nodata_val:
                    p[col] = None
                elif col == "landcover_class":
                    p[col] = int(v)
                else:
                    p[col] = round(v, 2)
    return points


def main():
    print("Loading positive + negative points...")
    points = load_points()
    n_pos = sum(1 for p in points if p["label"] == 1)
    n_neg = sum(1 for p in points if p["label"] == 0)
    print(f"  {n_pos} positive, {n_neg} negative, {len(points)} total")

    print("Sampling elevation/slope/aspect at each point...")
    points = sample_rasters(points)

    raster_cols = ["elevation_m", "slope_deg", "aspect_deg", "distance_to_stream_m", "landcover_class",
                   "soil_erodibility_k", "rusle_ls_factor", "rusle_c_factor",
                   "rainfall_erosivity_r", "soil_loss_tha_yr"]
    missing = [p for p in points if any(p[c] is None for c in raster_cols)]
    if missing:
        print(f"  WARNING: {len(missing)} points had nodata in at least one raster -- dropping them")
        points = [p for p in points if all(p[c] is not None for c in raster_cols)]

    out_path = PROCESSED / "training_table.csv"
    cols = ["lon", "lat", "elevation_m", "slope_deg", "aspect_deg",
            "distance_to_stream_m", "landcover_class",
            "soil_erodibility_k", "rusle_ls_factor", "rusle_c_factor",
            "rainfall_erosivity_r", "soil_loss_tha_yr", "label"]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        for p in points:
            writer.writerow({c: p[c] for c in cols})
    print(f"Wrote {out_path} ({len(points)} rows, {len(cols)} columns)")
    print(f"  columns: {cols}")
    print("\nNote for B (ML lead): lithology is NOT in this table -- both GSI source")
    print("portals (NGDR, BHUKOSH) are unreachable. Everything else the doc listed as")
    print("a 'core model input' is here now.")


if __name__ == "__main__":
    main()
