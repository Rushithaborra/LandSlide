"""Data-quality audit of every raster/vector collected in the broad
collection pass (docs/dataset_inventory.md). Checks bounds, CRS, resolution,
missing/NoData/invalid values, and coverage against the actual pilot AOI --
does not resample, reproject, or otherwise transform anything. Read-only.
"""
import json
import zipfile

import numpy as np
import pyproj
import rasterio
from shapely.geometry import box, shape
from shapely.ops import transform as shp_transform

from scripts.ml.ml_config import DEFAULT_CONFIG

# Pilot AOI = the actual bounding box of our 777 GSI points (road-corridor
# scope, not the full state) -- this is what coverage is checked against.
PILOT_BOUNDS = (88.077111, 27.08275, 88.840194, 27.749111)  # (minx, miny, maxx, maxy)
PILOT_BOX = box(*PILOT_BOUNDS)


def audit_raster(name: str, path: str, expect_crs: str | None = None) -> None:
    print(f"\n--- {name} ---")
    print(f"path: {path}")
    with rasterio.open(path) as src:
        print(f"CRS: {src.crs}")
        print(f"resolution: {src.res}")
        print(f"shape: {src.shape}")
        print(f"bounds: {src.bounds}")
        print(f"nodata: {src.nodata}")
        print(f"dtype: {src.dtypes}")

        # Pilot AOI is defined in WGS84 degrees -- reproject it to whatever
        # CRS this raster uses before comparing bounds/windowing, otherwise
        # a UTM raster's meter-valued bounds get compared against degree
        # values and every non-4326 raster looks like it has zero coverage.
        if str(src.crs) == "EPSG:4326":
            pilot_in_raster_crs = PILOT_BOX
            pilot_bounds_in_raster_crs = PILOT_BOUNDS
        else:
            transformer = pyproj.Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
            pilot_in_raster_crs = shp_transform(transformer.transform, PILOT_BOX)
            pilot_bounds_in_raster_crs = pilot_in_raster_crs.bounds

        raster_box = box(*src.bounds)
        covers_pilot = raster_box.contains(pilot_in_raster_crs)
        print(f"covers pilot AOI: {covers_pilot}")

        from rasterio.windows import from_bounds
        try:
            win = from_bounds(*pilot_bounds_in_raster_crs, src.transform)
            arr = src.read(1, window=win, boundless=True, fill_value=src.nodata or np.nan)
        except Exception as e:
            print(f"could not window-read pilot AOI: {e}")
            arr = src.read(1)

        arr = arr.astype(np.float64)
        total = arr.size
        nodata_mask = (arr == src.nodata) if src.nodata is not None else np.zeros_like(arr, dtype=bool)
        nan_mask = np.isnan(arr)
        inf_mask = np.isinf(arr)
        valid = arr[~nodata_mask & ~nan_mask & ~inf_mask]

        print(f"pixels in pilot-AOI window: {total}")
        print(f"  NoData: {nodata_mask.sum()} ({nodata_mask.sum()/total*100:.1f}%)")
        print(f"  NaN: {nan_mask.sum()} ({nan_mask.sum()/total*100:.1f}%)")
        print(f"  Inf: {inf_mask.sum()} ({inf_mask.sum()/total*100:.1f}%)")
        if valid.size:
            print(f"  valid value range: {valid.min():.2f} to {valid.max():.2f}, mean {valid.mean():.2f}")
        else:
            print("  NO VALID PIXELS in pilot AOI window")

    if expect_crs and str(src.crs) != expect_crs:
        print(f"WARNING: expected CRS {expect_crs}, got {src.crs}")


def audit_vector_geojson(name: str, path: str) -> None:
    print(f"\n--- {name} ---")
    print(f"path: {path}")
    with open(path) as f:
        data = json.load(f)
    feats = data["features"]
    print(f"feature count: {len(feats)}")
    if not feats:
        print("EMPTY -- no features")
        return
    geoms = [shape(f["geometry"]) for f in feats]
    xs = [g.x if g.geom_type == "Point" else g.centroid.x for g in geoms]
    ys = [g.y if g.geom_type == "Point" else g.centroid.y for g in geoms]
    bounds = (min(xs), min(ys), max(xs), max(ys))
    print(f"bounds: {bounds}")
    in_pilot = sum(1 for x, y in zip(xs, ys) if PILOT_BOUNDS[0] <= x <= PILOT_BOUNDS[2]
                   and PILOT_BOUNDS[1] <= y <= PILOT_BOUNDS[3])
    print(f"features within pilot AOI bbox: {in_pilot}/{len(feats)} ({in_pilot/len(feats)*100:.1f}%)")
    null_geom = sum(1 for g in geoms if g.is_empty)
    print(f"null/empty geometries: {null_geom}")


def audit_lithology_grid(path: str) -> None:
    print("\n--- GLiM lithology (0.5 deg gridded) ---")
    print(f"path: {path}")
    with zipfile.ZipFile(path) as z:
        with z.open("glim_wgs84_0point5deg.txt.asc") as f:
            header_lines = [f.readline().decode().strip() for _ in range(6)]
    header = dict(line.split() for line in header_lines)
    print("ASCII grid header:", header)
    cellsize = float(header["cellsize"])
    pilot_width_deg = PILOT_BOUNDS[2] - PILOT_BOUNDS[0]
    pilot_height_deg = PILOT_BOUNDS[3] - PILOT_BOUNDS[1]
    cells_across_pilot_x = pilot_width_deg / cellsize
    cells_across_pilot_y = pilot_height_deg / cellsize
    print(f"grid cell size: {cellsize} deg (~{cellsize*111:.0f}km at the equator)")
    print(f"pilot AOI is {pilot_width_deg:.2f} x {pilot_height_deg:.2f} deg -> only "
          f"{cells_across_pilot_x:.2f} x {cells_across_pilot_y:.2f} grid cells across the ENTIRE pilot area")
    print("VERDICT: too coarse -- would assign one (or at most two-three) lithology values "
          "to the whole pilot corridor. Not usable as a per-point predictor.")


def main() -> None:
    print("=" * 70)
    print("RASTER AUDITS")
    print("=" * 70)
    audit_raster("Copernicus GLO-30 DEM (native, EPSG:4326)",
                  "data/raw/dem/N27_00_E088_00.tif", expect_crs="EPSG:4326")
    audit_raster("Copernicus GLO-30 DEM (reprojected, EPSG:32645)",
                  str(DEFAULT_CONFIG.paths.dem_utm_path), expect_crs="EPSG:32645")
    audit_raster("ESA WorldCover 10m 2021",
                  "data/raw/landcover/ESA_WorldCover_10m_2021_v200_N27E087_Map.tif")
    for prop in ["clay", "sand", "silt", "soc"]:
        audit_raster(f"SoilGrids {prop} 0-5cm mean",
                      f"data/raw/soilgrids/{prop}_0-5cm_mean_sikkim.tif")
    audit_raster("WorldPop India 2020 (1km, whole-India file)",
                  "data/raw/population/ind_ppp_2020_1km_Aggregated.tif")

    print("\n" + "=" * 70)
    print("VECTOR AUDITS")
    print("=" * 70)
    audit_vector_geojson("Roads (OSM)", "data/raw/sikkim_roads.geojson")
    audit_vector_geojson("Villages/hamlets (OSM)", "data/raw/osm_extras/villages_hamlets.geojson")
    audit_vector_geojson("Buildings centroids (OSM)", "data/raw/osm_extras/buildings_centroids.geojson")
    audit_vector_geojson("Hospitals/schools (OSM)", "data/raw/osm_extras/hospitals_schools.geojson")
    audit_vector_geojson("Infrastructure (OSM)", "data/raw/osm_extras/infrastructure.geojson")

    print("\n" + "=" * 70)
    print("LITHOLOGY AUDIT")
    print("=" * 70)
    audit_lithology_grid("data/raw/lithology/GLiM_0.5deg_gridded.zip")


if __name__ == "__main__":
    main()
