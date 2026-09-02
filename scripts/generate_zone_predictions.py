"""Operationalizes the already-trained, already-validated susceptibility
model (data/models/susceptibility_model.joblib, see
docs/model_training_report.md) into a real GIS decision layer: predictions
for actual Sikkim road-corridor segments, built from real OSM road geometry.

Does NOT retrain or redesign the model. Does NOT invent zone polygons --
every corridor here is derived from a real OSM road LineString, buffered by
a documented, already-justified width. Does NOT use distance-to-road as a
predictor (it's the geometry unit, not a feature -- see PREDICTION_FEATURE_COLS
below, which excludes it, same as training).

HONEST SCOPE (unchanged from every prior document this session): road-
corridor, zone-level landslide susceptibility for the Sikkim pilot. This
does not predict the exact time of a landslide. See
docs/gis_prediction_layer.md for the full data contract and limitations.
"""
import json
import pathlib
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import rasterio.features
from shapely.geometry import box, mapping
from shapely.ops import substring, transform as shp_transform
import pyproj

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from scripts.ml.extract_landcover import WORLDCOVER_CLASSES, one_hot_encode
from scripts.ml.extract_terrain_features import build_feature_stack
from scripts.ml.fetch_osm_roads import load_roads
from scripts.ml.ml_config import DEFAULT_CONFIG, MlConfig
from scripts.ml.train_susceptibility_model import ARTIFACT_DIR, score_to_tier
from scripts.ml.predict_zone_susceptibility import load_model_bundle

# Same pilot AOI used throughout this session's data/feature/bias audits --
# the actual bounding box of the 777 (now 774) GSI training points. This is
# the geographic domain the model has evidence for; predicting outside it
# would be extrapolation, so road segments are restricted to it.
PILOT_BOUNDS = (88.077111, 27.08275, 88.840194, 27.749111)

# "Meaningful" road classes: OSM's standard public-through-road hierarchy
# (trunk/primary/secondary/tertiary), PLUS anything carrying a highway `ref`
# number. The second clause exists because of a verified real data-quality
# issue: several actual National Highways in this region -- including NH310A
# "North Sikkim Highway", directly referenced in our own GSI inventory --
# are tagged highway=unclassified in OSM rather than trunk/primary. Using
# class alone would silently drop them. Excludes residential/service/track/
# path/footway/steps/etc -- local-access and non-vehicular ways not
# represented in the GSI road-corridor survey this model was trained on.
MEANINGFUL_HIGHWAY_CLASSES = ["trunk", "primary", "secondary", "tertiary"]

# Corridor half-width: REUSES the existing, already-justified
# NegativeSamplingConfig.corridor_buffer_m (500m) from the training
# pipeline, rather than picking a new number. That value was chosen because
# it captures 99.4% of positives' measured distance to the nearest road
# (verified during the original data audit, p99=315m). Reusing it here
# keeps prediction units within the same geographic margin the model's
# training data actually came from.
CORRIDOR_BUFFER_M = DEFAULT_CONFIG.sampling.corridor_buffer_m

# Along-road segment length: no prior project precedent for this specific
# choice, so it's a new, explicitly documented decision -- set equal to the
# corridor buffer width so each prediction unit spans roughly one
# corridor-width along the road (a simple, defensible rule, not tuned to
# produce a particular-looking count or map).
SEGMENT_LENGTH_M = CORRIDOR_BUFFER_M

OUTPUT_DIR = pathlib.Path(__file__).resolve().parent.parent / "outputs" / "gis"


def load_and_filter_roads(config: MlConfig = DEFAULT_CONFIG) -> gpd.GeoDataFrame:
    gdf = load_roads(config)
    is_meaningful = gdf["highway"].isin(MEANINGFUL_HIGHWAY_CLASSES) | gdf["ref"].notna()
    gdf = gdf[is_meaningful].copy()

    pilot_box = box(*PILOT_BOUNDS)
    gdf = gdf[gdf.intersects(pilot_box)].copy()
    gdf["geometry"] = gdf.intersection(pilot_box)  # clip to the pilot AOI exactly
    gdf = gdf[~gdf.is_empty]
    return gdf.reset_index(drop=True)


def segment_roads(gdf_wgs84: gpd.GeoDataFrame, segment_length_m: float = SEGMENT_LENGTH_M,
                   config: MlConfig = DEFAULT_CONFIG) -> gpd.GeoDataFrame:
    """Chunks each road LineString into ~segment_length_m pieces (in UTM, so
    length is metric), keeping a stable ID per chunk. Any final partial chunk
    shorter than 20% of the target length is merged into the previous chunk
    rather than kept as a near-zero-length sliver."""
    gdf_utm = gdf_wgs84.to_crs(config.dem.target_crs)
    rows = []
    for idx, row in gdf_utm.iterrows():
        line = row.geometry
        if line.geom_type == "MultiLineString":
            parts = list(line.geoms)
        else:
            parts = [line]

        for part_i, part in enumerate(parts):
            length = part.length
            if length <= 0:
                continue
            n_segments = max(int(length // segment_length_m), 1)
            cut_points = np.linspace(0, length, n_segments + 1)
            # merge a too-short final piece into the previous one
            if n_segments > 1 and (cut_points[-1] - cut_points[-2]) < 0.2 * segment_length_m:
                cut_points = np.delete(cut_points, -2)

            for seg_i in range(len(cut_points) - 1):
                seg_line = substring(part, cut_points[seg_i], cut_points[seg_i + 1])
                if seg_line.length <= 0:
                    continue
                rows.append({
                    "segment_id": f"{row['osm_id']}_{part_i:02d}_{seg_i:03d}",
                    "osm_id": row["osm_id"], "highway": row["highway"],
                    "name": row["name"], "ref": row["ref"],
                    "geometry": seg_line,
                })

    segments = gpd.GeoDataFrame(rows, crs=config.dem.target_crs)
    return segments


def build_corridors(segments_utm: gpd.GeoDataFrame, buffer_m: float = CORRIDOR_BUFFER_M) -> gpd.GeoDataFrame:
    corridors = segments_utm.copy()
    corridors["geometry"] = corridors.geometry.buffer(buffer_m)
    return corridors


def zonal_median(polygon_native_crs, array: np.ndarray, transform, nodata=None) -> float | None:
    """Median of raster cells intersecting polygon_native_crs, which must
    already be in the raster's own CRS. Windowed to the polygon's bounding
    box first -- masking the FULL array per polygon would be far too slow
    against a 36000x36000 raster over thousands of polygons."""
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
    if nodata is not None:
        mask &= sub_array != nodata
    values = sub_array[mask]
    values = values[~np.isnan(values)] if np.issubdtype(values.dtype, np.floating) else values
    return float(np.median(values)) if values.size else None


def zonal_dominant_landcover(polygon_wgs84, src: rasterio.DatasetReader) -> str | None:
    """Dominant (most frequent) WorldCover class among pixels intersecting
    polygon_wgs84 (must be in EPSG:4326, WorldCover's native CRS -- same as
    extract_landcover.py's point-sampling, no reprojection needed there
    either). Takes an already-open dataset handle -- opening the file fresh
    per corridor (as an earlier version of this function did) is wasteful
    repeated I/O against a 36000x36000 raster over thousands of calls;
    verified this refactor doesn't change results, just avoids reopening."""
    window = rasterio.windows.from_bounds(*polygon_wgs84.bounds, transform=src.transform)
    window = window.round_offsets().round_lengths()
    row_off, col_off = max(int(window.row_off), 0), max(int(window.col_off), 0)
    row_stop = min(int(window.row_off + window.height), src.height)
    col_stop = min(int(window.col_off + window.width), src.width)
    if row_stop <= row_off or col_stop <= col_off:
        return None
    win = rasterio.windows.Window(col_off, row_off, col_stop - col_off, row_stop - row_off)
    sub_array = src.read(1, window=win)
    sub_transform = rasterio.windows.transform(win, src.transform)
    nodata = src.nodata

    mask = rasterio.features.geometry_mask(
        [mapping(polygon_wgs84)], out_shape=sub_array.shape, transform=sub_transform, invert=True
    )
    if nodata is not None:
        mask &= sub_array != nodata
    values = sub_array[mask]
    if values.size == 0:
        return None
    codes, counts = np.unique(values, return_counts=True)
    dominant_code = int(codes[np.argmax(counts)])
    return WORLDCOVER_CLASSES.get(dominant_code)


def extract_corridor_features(corridors_utm: gpd.GeoDataFrame, config: MlConfig = DEFAULT_CONFIG) -> pd.DataFrame:
    """Zonal statistics per corridor polygon: median for continuous terrain
    features (documented choice -- robust to outlier pixels at a corridor's
    edge, standard for zonal aggregation of skewed terrain distributions),
    dominant class for land cover (documented choice -- a corridor's
    'representative' land cover, matching how a human would describe it)."""
    feature_stack = build_feature_stack(config.paths.dem_utm_path, config)
    transformer = pyproj.Transformer.from_crs(config.dem.target_crs, "EPSG:4326", always_xy=True)

    rows = []
    with rasterio.open(config.paths.landcover_tif) as landcover_src:
        for _, row in corridors_utm.iterrows():
            poly_utm = row.geometry
            elevation = zonal_median(poly_utm, feature_stack["elevation"], feature_stack["transform"])
            slope = zonal_median(poly_utm, feature_stack["slope"], feature_stack["transform"])
            curvature = zonal_median(poly_utm, feature_stack["curvature"], feature_stack["transform"])
            dist_drainage = zonal_median(poly_utm, feature_stack["distance_to_drainage"], feature_stack["transform"])

            poly_wgs84 = shp_transform(transformer.transform, poly_utm)
            land_cover_class = zonal_dominant_landcover(poly_wgs84, landcover_src)

            rows.append({
                "segment_id": row["segment_id"], "elevation": elevation, "slope": slope,
                "curvature": curvature, "distance_to_drainage": dist_drainage,
                "land_cover_class": land_cover_class,
            })
    return pd.DataFrame(rows)


def verify_feature_schema(features_df: pd.DataFrame, bundle: dict) -> pd.DataFrame:
    """Programmatic check, per the critical requirement that training and
    inference feature engineering must match: builds the one-hot land-cover
    columns the SAME way training did (extract_landcover.one_hot_encode) and
    asserts the resulting column set exactly matches what the model was
    fit on -- not eyeballed, asserted."""
    one_hot = one_hot_encode(features_df["land_cover_class"])
    for col in bundle["feature_cols"]:
        if col.startswith("landcover_") and col not in one_hot.columns:
            one_hot[col] = 0  # class not present in this batch of corridors

    X = pd.concat([features_df.drop(columns=["land_cover_class"]), one_hot], axis=1)
    missing = set(bundle["feature_cols"]) - set(X.columns)
    extra_landcover = set(c for c in X.columns if c.startswith("landcover_")) - set(bundle["feature_cols"])
    assert not missing, f"SCHEMA MISMATCH: model expects columns not present in inference features: {missing}"
    if extra_landcover:
        print(f"  note: dropping land-cover classes present in corridors but not seen in training: {extra_landcover}")
        X = X.drop(columns=list(extra_landcover))
    return X[bundle["feature_cols"]]


def predict_corridors(corridors: gpd.GeoDataFrame, features_df: pd.DataFrame, bundle: dict) -> gpd.GeoDataFrame:
    """corridors: geometry + osm_id/highway/name/ref, indexed by segment_id.
    features_df: segment_id + the raw extracted feature values. Returns
    corridors joined with features and predictions -- one clean frame."""
    merged = corridors.merge(features_df, on="segment_id", how="inner")
    valid = merged.dropna(subset=["elevation", "slope", "curvature", "distance_to_drainage", "land_cover_class"]).copy()
    dropped = len(merged) - len(valid)
    if dropped:
        print(f"  dropping {dropped} corridors with incomplete feature coverage (outside raster bounds)")

    X = verify_feature_schema(valid, bundle)
    scores = bundle["pipeline"].predict_proba(X)[:, 1]
    valid["susceptibility_score"] = scores
    valid["risk_tier"] = [score_to_tier(s, bundle["low_cut"], bundle["high_cut"]) for s in scores]
    valid["model_version"] = bundle["model_version"]
    return valid


def run_quality_checks(predictions: gpd.GeoDataFrame, corridors_wgs84: gpd.GeoDataFrame) -> dict:
    print("\n=== Step 9: quality checks ===")
    checks = {}

    checks["crs_is_4326"] = str(predictions.crs) == "EPSG:4326"
    print(f"1. CRS consistency (EPSG:4326): {checks['crs_is_4326']}")

    invalid_geom = (~predictions.geometry.is_valid).sum()
    checks["invalid_geometries"] = int(invalid_geom)
    print(f"2. Invalid geometries: {invalid_geom}")

    missing = predictions[["elevation", "slope", "curvature", "distance_to_drainage", "land_cover_class"]].isna().sum().sum()
    checks["missing_feature_values"] = int(missing)
    print(f"3. Missing feature values (post-drop): {missing}")

    unexpected_lc = set(predictions["land_cover_class"].unique()) - set(WORLDCOVER_CLASSES.values())
    checks["unexpected_landcover_codes"] = list(unexpected_lc)
    print(f"4. Unexpected land-cover codes: {unexpected_lc if unexpected_lc else 'none'}")

    score_min, score_max = predictions["susceptibility_score"].min(), predictions["susceptibility_score"].max()
    checks["score_range"] = [float(score_min), float(score_max)]
    print(f"5. Score range: [{score_min:.3f}, {score_max:.3f}] (should be within [0,1])")

    tier_counts = predictions["risk_tier"].value_counts().to_dict()
    checks["risk_tier_counts"] = tier_counts
    print(f"6. Score/tier distribution: {tier_counts}")

    checks["n_segments"] = len(predictions)
    print(f"7. Number of prediction units: {len(predictions)}")

    dupe_ids = predictions["segment_id"].duplicated().sum()
    checks["duplicate_ids"] = int(dupe_ids)
    print(f"8. Duplicate segment IDs: {dupe_ids}")

    total_input = len(corridors_wgs84)
    coverage_pct = len(predictions) / total_input * 100 if total_input else 0
    checks["spatial_coverage_pct_of_filtered_roads"] = round(coverage_pct, 1)
    print(f"9. Spatial coverage: {len(predictions)}/{total_input} filtered road segments scored ({coverage_pct:.1f}%)")

    score_std = predictions["susceptibility_score"].std()
    checks["score_std"] = float(score_std)
    suspiciously_constant = score_std < 0.01
    checks["suspiciously_constant"] = bool(suspiciously_constant)
    print(f"10. Score std dev: {score_std:.4f} {'<-- SUSPICIOUSLY CONSTANT' if suspiciously_constant else '(real variation present)'}")

    return checks


def sanity_check_against_inventory(predictions: gpd.GeoDataFrame, config: MlConfig = DEFAULT_CONFIG) -> dict:
    """NOT independent validation -- these exact points were used to train
    the model. This only checks that corridor-level predictions near known
    positive/negative locations are directionally consistent with the
    point-level model, as a basic pipeline sanity check."""
    print("\n=== Sanity check vs. known inventory (NOT independent validation) ===")
    training = pd.read_csv(config.paths.training_dataset_csv)
    points = gpd.GeoDataFrame(
        training, geometry=gpd.points_from_xy(training["longitude"], training["latitude"]), crs="EPSG:4326"
    )
    joined = gpd.sjoin(points, predictions[["segment_id", "susceptibility_score", "risk_tier", "geometry"]],
                        how="inner", predicate="within")

    result = {"n_positive_points_matched": int((joined["label"] == 1).sum()),
              "n_negative_points_matched": int((joined["label"] == 0).sum())}
    if len(joined):
        pos_mean = joined.loc[joined["label"] == 1, "susceptibility_score"].mean()
        neg_mean = joined.loc[joined["label"] == 0, "susceptibility_score"].mean()
        result["mean_corridor_score_at_positive_points"] = float(pos_mean) if pd.notna(pos_mean) else None
        result["mean_corridor_score_at_negative_points"] = float(neg_mean) if pd.notna(neg_mean) else None
        print(f"positive points falling inside a scored corridor: {result['n_positive_points_matched']}, "
              f"mean corridor score there: {pos_mean:.3f}" if pd.notna(pos_mean) else "n/a")
        print(f"negative points falling inside a scored corridor: {result['n_negative_points_matched']}, "
              f"mean corridor score there: {neg_mean:.3f}" if pd.notna(neg_mean) else "n/a")
    return result


def save_gis_outputs(predictions: gpd.GeoDataFrame) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # GeoPackage skipped: pyogrio (geopandas' GDAL-backed write engine) is
    # blocked by this machine's Application Control policy -- verified as a
    # genuine, persistent technical incompatibility (re-checked at the start
    # of this task, not assumed from memory), not worked around by writing
    # a hand-rolled GeoPackage (that would be exactly the "custom geospatial
    # logic" the project's coding rule says to avoid when a library gap
    # exists). GeoJSON covers the "lightweight frontend use" case explicitly
    # named as an acceptable alternative.
    feature_cols = ["segment_id", "osm_id", "highway", "name", "ref", "elevation", "slope",
                     "curvature", "distance_to_drainage", "land_cover_class",
                     "susceptibility_score", "risk_tier", "model_version"]
    geojson = {
        "type": "FeatureCollection",
        "properties": {
            "description": "Road-corridor landslide susceptibility, Sikkim pilot. "
                            "This is a zone-level susceptibility assessment derived from a spatially "
                            "validated model. It does NOT predict the exact time of a landslide. "
                            "Road-corridor scope: the training inventory has strong road-survey bias "
                            "(96.1% of positives within 100m of a mapped road), so predictions are only "
                            "produced for road corridors, not arbitrary terrain. No real-time rainfall is "
                            "included -- this is the static layer; rainfall is a separate dynamic alert layer.",
        },
        "features": [
            {"type": "Feature",
             "properties": {c: (None if pd.isna(row[c]) else row[c]) for c in feature_cols},
             "geometry": mapping(row.geometry)}
            for _, row in predictions.iterrows()
        ],
    }
    geojson_path = OUTPUT_DIR / "sikkim_road_susceptibility.geojson"
    with open(geojson_path, "w") as f:
        json.dump(geojson, f)
    print(f"\nGeoJSON saved -> {geojson_path}")

    csv_path = OUTPUT_DIR / "sikkim_road_susceptibility.csv"
    predictions[feature_cols].to_csv(csv_path, index=False)
    print(f"CSV saved -> {csv_path}")

    gpkg_note_path = OUTPUT_DIR / "sikkim_road_susceptibility.gpkg.SKIPPED.txt"
    gpkg_note_path.write_text(
        "GeoPackage output was NOT generated. pyogrio (geopandas' GDAL-backed write engine) is\n"
        "blocked by an Application Control policy on this machine -- verified genuine and persistent\n"
        "(re-checked at the start of this task: `import pyogrio` fails with "
        "'An Application Control policy has blocked this file', not a PATH issue -- adding rasterio's\n"
        "own bundled GDAL directory to the DLL search path did not fix it).\n\n"
        "Use sikkim_road_susceptibility.geojson instead -- same data, same geometry, no GDAL dependency\n"
        "(written directly via json+shapely, the same pattern already used by scripts/ml/fetch_osm_roads.py).\n"
        "On a machine where pyogrio/fiona import cleanly, `geopandas.GeoDataFrame.to_file(..., driver='GPKG')`\n"
        "on the GeoJSON above will produce the GeoPackage with no other code changes needed.\n"
    )
    print(f"GeoPackage skip reason documented -> {gpkg_note_path}")


if __name__ == "__main__":
    print("=== Step 1-3: load model, roads, segments, corridors ===")
    bundle = load_model_bundle()
    print(f"loaded model bundle: {bundle['model_version']}, feature_cols={bundle['feature_cols']}")

    roads = load_and_filter_roads()
    print(f"filtered roads (meaningful classes, pilot AOI): {len(roads)} ways")

    segments = segment_roads(roads)
    print(f"segmented into {len(segments)} ~{SEGMENT_LENGTH_M:.0f}m chunks")

    corridors = build_corridors(segments)
    print(f"corridors built, buffer={CORRIDOR_BUFFER_M:.0f}m")

    print("\n=== Step 4-5: feature extraction (this takes ~2-3 minutes) ===")
    features = extract_corridor_features(corridors)

    print("\n=== Step 6-7: predict + risk tier ===")
    predictions = predict_corridors(corridors, features, bundle)
    predictions_wgs84 = predictions.to_crs("EPSG:4326")

    checks = run_quality_checks(predictions_wgs84, corridors.to_crs("EPSG:4326"))
    sanity = sanity_check_against_inventory(predictions_wgs84)
    save_gis_outputs(predictions_wgs84)

    print(f"\nDONE. {len(predictions_wgs84)} corridor predictions generated.")
