"""
Operationalizes a state's already-trained susceptibility model
(data/models/<state>/model.joblib, from scripts/22) into real road-corridor
zone predictions, the same way master's scripts/generate_zone_predictions.py
does for Sikkim/Assam -- adapted here for this project's RUSLE-based feature
schema (elevation_m, slope_deg, aspect_deg, distance_to_stream_m,
landcover_class, soil_erodibility_k, rusle_ls_factor, rusle_c_factor,
rainfall_erosivity_r, soil_loss_tha_yr) instead of Sikkim's schema.

Does NOT retrain or redesign the model (scripts/22 already did that, with
honest spatial-CV validation). Does NOT invent zone polygons -- every
corridor here is a real OSM road LineString, buffered by the same 500m
half-width already justified and used for Sikkim/Assam (captures ~99% of
GSI positives' measured distance to the nearest road; reusing it keeps
prediction units within the same geographic margin the model's training
data actually came from, rather than picking a new number for this state).

Requires scripts/18 (terrain/RUSLE rasters), scripts/19 (roads -- must be
re-run after this script's own name/ref fix if an older roads.geojson
without those tags is already cached) and scripts/22 (trained model) to
have already produced this state's outputs.

Usage: python3 scripts/23_generate_state_zone_predictions.py <state_slug>

Output: outputs/gis/<state_slug>_road_susceptibility.geojson
Same property shape master's script produces (segment_id, osm_id, highway,
name, ref, susceptibility_score, risk_tier, model_version, plus this
schema's own 10 feature values) so it can be pushed into the live database
via scripts/integrate_zone_predictions.py (from the master/backend repo)
completely unmodified -- that script already reads exactly this shape.

Note: written for this worktree's Python 3.9 -- uses typing.Optional
rather than the `X | None` union syntax (3.10+ only).
"""
import json
import sys
from pathlib import Path
from typing import Optional

import geopandas as gpd
import joblib
import numpy as np
import pandas as pd
import rasterio
import rasterio.features
from pyproj import Transformer
from shapely.geometry import mapping
from shapely.ops import substring, transform as shp_transform

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ner_config import STATE_CONFIGS

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
MODELS = ROOT / "data" / "models"
OUTPUT_DIR = ROOT / "outputs" / "gis"
NODATA = -9999.0

# Same road-class filter master's generate_zone_predictions.py uses for
# Sikkim/Assam -- real public through-roads, plus anything carrying a
# highway `ref` (some real National Highways in this region are tagged
# highway=unclassified in OSM rather than trunk/primary; class alone would
# silently drop them). Deliberately narrower than script 19's own fetch
# (which pulls a broader "drivable classes" set for road-proximity bias
# measurement) -- zone generation only scores the state's real, named/
# classified through-road network, not every residential/service way.
MEANINGFUL_HIGHWAY_CLASSES = {"trunk", "primary", "secondary", "tertiary"}

# Same 500m corridor half-width already justified and used for Sikkim/Assam
# (see module docstring) -- one shared convention across every state in
# this project, not a new number picked per state.
CORRIDOR_BUFFER_M = 500.0
SEGMENT_LENGTH_M = 500.0

FEATURE_COLS = [
    "elevation_m", "slope_deg", "aspect_deg", "distance_to_stream_m",
    "landcover_class", "soil_erodibility_k", "rusle_ls_factor",
    "rusle_c_factor", "rainfall_erosivity_r", "soil_loss_tha_yr",
]

RASTER_FILES = {
    "elevation_m": "dem_{slug}.tif",
    "slope_deg": "slope_deg_{slug}.tif",
    "aspect_deg": "aspect_deg_{slug}.tif",
    "distance_to_stream_m": "distance_to_stream_m_{slug}.tif",
    "soil_erodibility_k": "rusle_k_factor_{slug}.tif",
    "rusle_ls_factor": "rusle_ls_factor_{slug}.tif",
    "rusle_c_factor": "rusle_c_factor_{slug}.tif",
    "rainfall_erosivity_r": "rusle_r_factor_{slug}.tif",
    "soil_loss_tha_yr": "rusle_soil_loss_annual_{slug}.tif",
}
LANDCOVER_NODATA = 255


def load_and_filter_roads(slug: str, bbox: tuple) -> gpd.GeoDataFrame:
    with open(RAW / f"{slug}_roads.geojson") as f:
        gj = json.load(f)
    gdf = gpd.GeoDataFrame.from_features(gj["features"], crs="EPSG:4326")
    missing_tags = {"name", "ref"} - set(gdf.columns)
    if missing_tags:
        raise RuntimeError(
            f"{slug}_roads.geojson is missing {missing_tags} -- it was fetched before scripts/19's "
            f"name/ref fix. Delete data/raw/{slug}_roads.geojson and data/raw/{slug}_negative_samples.csv "
            "and re-run scripts/19 to refetch with those tags included, then retry this script."
        )
    is_meaningful = gdf["highway"].isin(MEANINGFUL_HIGHWAY_CLASSES) | gdf["ref"].notna()
    gdf = gdf[is_meaningful].copy()

    # Clip to the state's REAL boundary polygon, not its bounding-box
    # rectangle. Roads are fetched over the rectangle (needed for the
    # Overpass query), but an irregularly-shaped state's rectangle also
    # covers large chunks of neighboring states -- verified on Arunachal
    # Pradesh: only 32% of "within bbox" roads were actually inside the
    # real polygon, median distance of the rest ~26km outside it. Clipping
    # here (once, cheaply) avoids wastefully segmenting/buffering/scoring
    # thousands of corridors for roads that were never in this state, which
    # is what caused most of the "dropped -- incomplete feature coverage"
    # corridors downstream (the terrain rasters are correctly clipped to
    # this same real polygon, so those roads had no data to be scored with
    # regardless -- this fix just stops computing them in the first place).
    with open(RAW / f"{slug}_boundary.geojson") as f:
        boundary_gj = json.load(f)
    boundary = gpd.GeoDataFrame.from_features(boundary_gj["features"], crs="EPSG:4326").union_all()

    before = len(gdf)
    gdf = gdf[gdf.intersects(boundary)].copy()
    gdf["geometry"] = gdf.intersection(boundary)
    gdf = gdf[~gdf.is_empty]
    print(f"  {len(gdf)} meaningful road ways actually inside the state boundary "
          f"(of {before} within the fetch bbox, {len(gj['features'])} fetched total)")
    return gdf.reset_index(drop=True)


def segment_roads(gdf_wgs84: gpd.GeoDataFrame, dst_crs: str) -> gpd.GeoDataFrame:
    """Same chunking rule as master's script: ~SEGMENT_LENGTH_M pieces per
    road, in UTM/projected metres so length is real, a too-short final
    sliver merged into the previous chunk rather than kept near-zero."""
    gdf_utm = gdf_wgs84.to_crs(dst_crs)
    rows = []
    for _, row in gdf_utm.iterrows():
        line = row.geometry
        parts = list(line.geoms) if line.geom_type == "MultiLineString" else [line]
        for part_i, part in enumerate(parts):
            length = part.length
            if length <= 0:
                continue
            n_segments = max(int(length // SEGMENT_LENGTH_M), 1)
            cut_points = np.linspace(0, length, n_segments + 1)
            if n_segments > 1 and (cut_points[-1] - cut_points[-2]) < 0.2 * SEGMENT_LENGTH_M:
                cut_points = np.delete(cut_points, -2)
            for seg_i in range(len(cut_points) - 1):
                seg_line = substring(part, cut_points[seg_i], cut_points[seg_i + 1])
                if seg_line.length <= 0:
                    continue
                rows.append({
                    "segment_id": f"{row['osm_id']}_{part_i:02d}_{seg_i:03d}",
                    "osm_id": row["osm_id"], "highway": row["highway"],
                    "name": row["name"], "ref": row["ref"], "geometry": seg_line,
                })
    return gpd.GeoDataFrame(rows, crs=dst_crs)


def _largest_part_if_multipolygon(geom):
    """A handful of tight hairpin/near-self-touching road segments buffer
    into a MultiPolygon instead of a Polygon -- same real edge case
    verified in master's pipeline at Assam's scale. zones.geometry is
    strictly typed Polygon, so keep only the largest-area part."""
    if geom.geom_type == "MultiPolygon":
        return max(geom.geoms, key=lambda g: g.area)
    return geom


def build_corridors(segments_utm: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    corridors = segments_utm.copy()
    corridors["geometry"] = corridors.geometry.buffer(CORRIDOR_BUFFER_M)
    is_multi = corridors.geometry.geom_type == "MultiPolygon"
    if is_multi.any():
        print(f"  note: {is_multi.sum()} corridor(s) buffered into a MultiPolygon -- keeping largest part")
        corridors["geometry"] = corridors.geometry.apply(_largest_part_if_multipolygon)
    return corridors


def zonal_median(polygon_native_crs, array: np.ndarray, transform, nodata) -> Optional[float]:
    """Median of raster cells intersecting the polygon (already in the
    raster's own CRS), windowed to the polygon's bounding box first --
    masking the full array per polygon would be far too slow against a
    large raster over thousands of polygons. Same method as master's
    zonal_median (continuous features: median is robust to outlier pixels
    at a corridor's edge)."""
    window = rasterio.windows.from_bounds(*polygon_native_crs.bounds, transform=transform)
    window = window.round_offsets().round_lengths()
    row_off, col_off = max(int(window.row_off), 0), max(int(window.col_off), 0)
    row_stop = min(int(window.row_off + window.height), array.shape[0])
    col_stop = min(int(window.col_off + window.width), array.shape[1])
    if row_stop <= row_off or col_stop <= col_off:
        return None
    sub_array = array[row_off:row_stop, col_off:col_stop]
    sub_transform = rasterio.windows.transform(
        rasterio.windows.Window(col_off, row_off, col_stop - col_off, row_stop - row_off), transform
    )
    mask = rasterio.features.geometry_mask(
        [mapping(polygon_native_crs)], out_shape=sub_array.shape, transform=sub_transform, invert=True
    )
    mask &= sub_array != nodata if nodata is not None else True
    values = sub_array[mask]
    values = values[~np.isnan(values)] if np.issubdtype(values.dtype, np.floating) else values
    return float(np.median(values)) if values.size else None


def zonal_dominant_class(polygon_native_crs, array: np.ndarray, transform, nodata) -> Optional[int]:
    """Most-frequent land-cover class code among pixels intersecting the
    corridor -- the model was trained on the raw WorldCover integer code
    (scripts/20/22 never one-hot-encode landcover_class, unlike Sikkim's
    model on master), so this returns the code itself, not a class name."""
    window = rasterio.windows.from_bounds(*polygon_native_crs.bounds, transform=transform)
    window = window.round_offsets().round_lengths()
    row_off, col_off = max(int(window.row_off), 0), max(int(window.col_off), 0)
    row_stop = min(int(window.row_off + window.height), array.shape[0])
    col_stop = min(int(window.col_off + window.width), array.shape[1])
    if row_stop <= row_off or col_stop <= col_off:
        return None
    sub_array = array[row_off:row_stop, col_off:col_stop]
    sub_transform = rasterio.windows.transform(
        rasterio.windows.Window(col_off, row_off, col_stop - col_off, row_stop - row_off), transform
    )
    mask = rasterio.features.geometry_mask(
        [mapping(polygon_native_crs)], out_shape=sub_array.shape, transform=sub_transform, invert=True
    )
    mask &= sub_array != nodata
    values = sub_array[mask]
    if values.size == 0:
        return None
    codes, counts = np.unique(values, return_counts=True)
    return int(codes[np.argmax(counts)])


def extract_corridor_features(corridors_utm: gpd.GeoDataFrame, slug: str) -> pd.DataFrame:
    # Read each raster's full array + transform once, up front -- reading
    # per-corridor would reopen and re-read a large raster thousands of
    # times. Each `with` block closes its file handle immediately after the
    # read; only the in-memory array/transform are kept for the loop below.
    open_rasters = {}
    for col, fname_tpl in RASTER_FILES.items():
        with rasterio.open(PROCESSED / fname_tpl.format(slug=slug)) as src:
            open_rasters[col] = (src.read(1), src.transform)
    with rasterio.open(PROCESSED / f"landcover_{slug}.tif") as lc_src:
        lc_arr, lc_transform = lc_src.read(1), lc_src.transform

    rows = []
    for _, row in corridors_utm.iterrows():
        poly = row.geometry
        feats = {"segment_id": row["segment_id"]}
        for col, (arr, transform) in open_rasters.items():
            feats[col] = zonal_median(poly, arr, transform, NODATA)
        feats["landcover_class"] = zonal_dominant_class(poly, lc_arr, lc_transform, LANDCOVER_NODATA)
        rows.append(feats)

    return pd.DataFrame(rows)


def score_to_tier(score: float, low_cut: float, high_cut: float) -> str:
    if score < low_cut:
        return "low"
    if score < high_cut:
        return "moderate"
    return "high"


def run(slug: str):
    cfg = STATE_CONFIGS[slug]
    dst_crs = cfg["dst_crs"]
    display_name = cfg["display_name"]
    print(f"=== {display_name} road-corridor zone predictions ===")

    print("[1/5] Loading + filtering roads...")
    roads = load_and_filter_roads(slug, cfg["bbox"])
    if len(roads) == 0:
        raise RuntimeError(f"No meaningful road ways found for {slug} -- cannot generate corridors")

    print("[2/5] Segmenting into ~500m chunks and buffering into corridors...")
    segments = segment_roads(roads, dst_crs)
    corridors = build_corridors(segments)
    print(f"  {len(corridors)} corridor segments")

    print("[3/5] Extracting features (zonal median/dominant-class per corridor)...")
    features_df = extract_corridor_features(corridors, slug)

    print("[4/5] Scoring with the trained model (data/models/{}/model.joblib)...".format(slug))
    model_path = MODELS / slug / "model.joblib"
    if not model_path.exists():
        raise FileNotFoundError(f"{model_path} not found -- run scripts/22_train_state_model.py {slug} first")
    pipeline = joblib.load(model_path)

    merged = corridors.merge(features_df, on="segment_id", how="inner")
    valid = merged.dropna(subset=FEATURE_COLS).copy()
    dropped = len(merged) - len(valid)
    if dropped:
        print(f"  dropping {dropped} corridors with incomplete feature coverage (outside raster bounds)")

    X = valid[FEATURE_COLS].values
    scores = pipeline.predict_proba(X)[:, 1]
    valid["susceptibility_score"] = scores

    # Tier thresholds: tertiles of this state's own model predictions on the
    # corridor set being scored -- same method (tertile cutoffs, our own
    # choice not literature-sourced) master's train_susceptibility_model.py
    # documents for Sikkim/Assam, just computed here since scripts/22
    # doesn't persist thresholds itself.
    low_cut, high_cut = float(np.percentile(scores, 33)), float(np.percentile(scores, 67))
    print(f"  risk tier thresholds (tertiles of this batch's scores): low < {low_cut:.3f} <= moderate < {high_cut:.3f} <= high")
    valid["risk_tier"] = [score_to_tier(s, low_cut, high_cut) for s in scores]

    from datetime import datetime, timezone
    model_version = f"{slug}-random_forest-v1-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    valid["model_version"] = model_version

    print(f"  score range: [{scores.min():.3f}, {scores.max():.3f}], std: {scores.std():.4f}")
    tier_counts = valid["risk_tier"].value_counts().to_dict()
    print(f"  tier distribution: {tier_counts}")

    print("[5/5] Writing GeoJSON output...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    to_wgs = Transformer.from_crs(dst_crs, "EPSG:4326", always_xy=True)
    feature_cols = ["segment_id", "osm_id", "highway", "name", "ref"] + FEATURE_COLS + [
        "susceptibility_score", "risk_tier", "model_version",
    ]
    geojson = {
        "type": "FeatureCollection",
        "properties": {
            "description": f"Road-corridor landslide susceptibility, {display_name}. Zone-level "
                            "assessment from a spatially-validated (block CV) Random Forest model, "
                            "trained per state on real GSI landslide records + real terrain/soil/"
                            "RUSLE-erosion/rainfall features. Does NOT predict the exact time of a "
                            "landslide. Road-corridor scope, same as every other state in this "
                            "project -- predictions are only produced for real road corridors, not "
                            "arbitrary terrain. No real-time rainfall included here -- this is the "
                            "static layer; rainfall is a separate dynamic alert layer.",
        },
        "features": [
            {
                "type": "Feature",
                "properties": {c: (None if pd.isna(row[c]) else row[c]) for c in feature_cols},
                "geometry": mapping(shp_transform(to_wgs.transform, row.geometry)),
            }
            for _, row in valid.iterrows()
        ],
    }
    out_path = OUTPUT_DIR / f"{slug}_road_susceptibility.geojson"
    with open(out_path, "w") as f:
        json.dump(geojson, f)
    print(f"\nGeoJSON saved -> {out_path} ({len(valid)} zones)")


if __name__ == "__main__":
    run(sys.argv[1])
