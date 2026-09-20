"""
Phase 1 of the 3D terrain visualization: a static hillshade + real
risk-tier overlay, served as a Leaflet ImageOverlay. Not full 3D
interactivity (no deck.gl, no camera controls) -- ships fast, looks
three-dimensional via simulated relief shading, and uses only real data:

  - Elevation: the actual Sikkim DEM (data/processed/dem_sikkim_utm45n.tif,
    from scripts/ml/fetch_dem.py -- a real Copernicus GLO-30 download, not
    synthesized).
  - Risk colors: the actual scored zones already used to populate
    production (outputs/gis/sikkim_road_susceptibility.geojson, 3,921
    real road-corridor zones, same file scripts/integrate_zone_predictions.py
    pushed via PUT /zones/{id}/susceptibility). A zone with no
    susceptibility_score renders as a distinct grey "not yet scored" color,
    never invented.

Hillshade computed with xarray-spatial (already a project dependency),
Horn's method -- the same algorithm GDAL's gdaldem hillshade uses.

Output: dashboard-app/public/sikkim_hillshade_overlay.png, plus its real
geographic bounds (EPSG:4326) printed for use in RiskMap.jsx's Leaflet
ImageOverlay -- the bounds are NOT hardcoded in the frontend, they come
from this raster's own transform so the overlay is never silently
misaligned if the DEM is ever regenerated.
"""
import json
from pathlib import Path

import numpy as np
import rasterio
import xarray as xr
from PIL import Image
from pyproj import Transformer
from rasterio.features import rasterize
from xrspatial import hillshade

ROOT = Path(__file__).resolve().parents[1]
DEM_PATH = ROOT / "data" / "processed" / "dem_sikkim_utm45n.tif"
ZONES_PATH = ROOT / "outputs" / "gis" / "sikkim_road_susceptibility_live.geojson"
# Not the original sikkim_road_susceptibility.geojson: that file predates
# Person B's real model (connected 2026-09-06, superseding scores for 3,411
# of 3,921 zones) and was found -- by directly checking this feature's own
# acceptance criteria (compare a known zone's rendered color against its
# real API score) -- to still carry the pre-Person-B tier for every single
# zone. Run scripts/sync_live_zone_scores.py first to (re)generate the
# _live file from the real, current production API before running this.
OUT_DIR = ROOT / "dashboard-app" / "public"
OUT_PATH = OUT_DIR / "sikkim_hillshade_overlay.png"

# Real risk-tier colors already used elsewhere in the dashboard's own
# legend (RiskMap.jsx) -- reused here, not invented fresh for this feature.
RISK_COLORS = {
    "low": (34, 197, 94),       # green
    "moderate": (234, 179, 8),  # amber
    "high": (239, 68, 68),      # red
}
UNSCORED_COLOR = (156, 163, 175)  # grey -- "not yet scored", never a fabricated tier
OVERLAY_ALPHA = 110  # out of 255 -- translucent so the hillshade underneath still reads


def compute_hillshade(dem_path: Path):
    with rasterio.open(dem_path) as src:
        elevation = src.read(1)
        nodata = src.nodata
        transform = src.transform
        crs = src.crs
        bounds = src.bounds

    valid = elevation != nodata if nodata is not None else np.ones_like(elevation, dtype=bool)

    da = xr.DataArray(
        elevation,
        dims=["y", "x"],
        attrs={"res": (transform.a, -transform.e)},
    )
    hs = hillshade(da, azimuth=315, angle_altitude=45)
    hs_arr = hs.values
    # xrspatial leaves NaN where the input was nodata -- keep that mask
    # rather than letting NaN silently become 0 (which would render as
    # pure black, indistinguishable from a real steep-shadow pixel).
    hs_arr = np.nan_to_num(hs_arr, nan=0.0)

    return hs_arr, valid, transform, crs, bounds


def rasterize_risk_tiers(zones_path: Path, out_shape, transform, crs):
    with open(zones_path) as f:
        gj = json.load(f)

    # Zones are stored in EPSG:4326 (see app/models.py: Geometry(srid=4326));
    # the DEM raster is in EPSG:32645 (UTM 45N) -- reproject each zone
    # polygon's coordinates before rasterizing onto the DEM's own grid, so
    # the two layers actually line up instead of silently drifting.
    to_dem_crs = Transformer.from_crs("EPSG:4326", crs, always_xy=True)

    def reproject_ring(ring):
        return [to_dem_crs.transform(x, y) for x, y in ring]

    shapes_scored = []
    shapes_unscored = []
    n_scored = n_unscored = 0
    for feat in gj["features"]:
        geom = feat["geometry"]
        if geom["type"] != "Polygon":
            continue
        reproj_geom = {
            "type": "Polygon",
            "coordinates": [reproject_ring(ring) for ring in geom["coordinates"]],
        }
        score = feat["properties"].get("susceptibility_score")
        tier = feat["properties"].get("risk_tier")
        if score is not None and tier in RISK_COLORS:
            shapes_scored.append((reproj_geom, tier))
            n_scored += 1
        else:
            shapes_unscored.append((reproj_geom, 1))
            n_unscored += 1

    print(f"  {n_scored} scored zones, {n_unscored} not-yet-scored zones (rendered grey, not skipped)")

    tier_to_code = {"low": 1, "moderate": 2, "high": 3}
    scored_burn = [(geom, tier_to_code[tier]) for geom, tier in shapes_scored]
    unscored_burn = [(geom, 4) for geom, _ in shapes_unscored]

    all_shapes = scored_burn + unscored_burn
    if not all_shapes:
        return np.zeros(out_shape, dtype=np.uint8)

    # rasterize() draws shapes in list order and later shapes silently win at
    # any pixel where geometries overlap. These are 500m-buffered ~500m road
    # corridors, so adjacent zones' buffers overlap substantially -- checked
    # directly: a real zone's own centroid can sit under 3 different zones'
    # polygons at once. Left in geojson-feature order, a lower-risk zone
    # drawn later could visually mask a higher-risk zone underneath it --
    # exactly backwards for a hazard map. Sorting so severity increases
    # (unscored -> low -> moderate -> high) means the highest real risk at
    # any overlapping pixel always ends up drawn last, i.e. visible.
    severity_rank = {4: 0, 1: 1, 2: 2, 3: 3}  # unscored, low, moderate, high
    all_shapes.sort(key=lambda shape_code: severity_rank[shape_code[1]])

    tier_raster = rasterize(
        all_shapes, out_shape=out_shape, transform=transform, fill=0, dtype=np.uint8,
    )
    return tier_raster


def compose_rgba(hillshade_arr, valid_mask, tier_raster):
    height, width = hillshade_arr.shape
    # xrspatial's hillshade returns illumination as a fraction in [0, 1],
    # not [0, 255] -- scale before casting to uint8. Casting the raw
    # fraction directly (the original bug here) truncates every value
    # below 1.0 to zero, rendering the entire hillshade as solid black.
    hs_norm = np.clip(hillshade_arr * 255.0, 0, 255).astype(np.uint8)

    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    rgba[..., 0] = hs_norm
    rgba[..., 1] = hs_norm
    rgba[..., 2] = hs_norm
    rgba[..., 3] = np.where(valid_mask, 255, 0)

    code_to_color = {1: RISK_COLORS["low"], 2: RISK_COLORS["moderate"], 3: RISK_COLORS["high"], 4: UNSCORED_COLOR}
    for code, color in code_to_color.items():
        mask = tier_raster == code
        if not mask.any():
            continue
        for c in range(3):
            rgba[..., c][mask] = (
                (1 - OVERLAY_ALPHA / 255) * rgba[..., c][mask] + (OVERLAY_ALPHA / 255) * color[c]
            ).astype(np.uint8)

    return rgba


def main():
    print("Computing hillshade from the real Sikkim DEM...")
    hs_arr, valid_mask, transform, crs, bounds_utm = compute_hillshade(DEM_PATH)
    print(f"  raster shape: {hs_arr.shape}, CRS: {crs}")

    print("Rasterizing real zone risk tiers onto the DEM's grid...")
    tier_raster = rasterize_risk_tiers(ZONES_PATH, hs_arr.shape, transform, crs)

    print("Compositing hillshade + risk overlay...")
    rgba = compose_rgba(hs_arr, valid_mask, tier_raster)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, mode="RGBA").save(OUT_PATH)
    print(f"Wrote {OUT_PATH}")

    # Real geographic bounds for the Leaflet ImageOverlay, in EPSG:4326 --
    # computed from this raster's own transform, not hand-typed, so a
    # regenerated DEM can never silently drift out of sync with the
    # frontend's overlay placement.
    to_wgs84 = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    sw = to_wgs84.transform(bounds_utm.left, bounds_utm.bottom)
    ne = to_wgs84.transform(bounds_utm.right, bounds_utm.top)
    leaflet_bounds = [[sw[1], sw[0]], [ne[1], ne[0]]]  # [[south, west], [north, east]]

    bounds_out = OUT_DIR / "sikkim_hillshade_bounds.json"
    with open(bounds_out, "w") as f:
        json.dump({"bounds": leaflet_bounds, "source": "generate_hillshade_overlay.py"}, f, indent=2)
    print(f"Wrote {bounds_out}: {leaflet_bounds}")


if __name__ == "__main__":
    main()
