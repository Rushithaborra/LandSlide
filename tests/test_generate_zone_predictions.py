"""Tests for the road-corridor GIS prediction pipeline. Synthetic data
where possible (fast, no network/DEM needed); a couple of tests need the
real model bundle/DEM and are skipped if those artifacts aren't present."""
import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin
import geopandas as gpd
from shapely.geometry import LineString, Point, Polygon

from scripts.generate_zone_predictions import (
    build_corridors,
    score_to_tier,
    segment_roads,
    verify_feature_schema,
    zonal_median,
)
from scripts.ml.ml_config import DEFAULT_CONFIG


# --- segmentation + corridor geometry -----------------------------------


def test_segment_roads_produces_expected_chunk_count():
    # a straight 1200m line (in UTM-like coordinates) should split into
    # roughly 1200/500 = 2.4 -> 2 chunks (short final piece merged back)
    utm_crs = DEFAULT_CONFIG.dem.target_crs
    line = LineString([(0, 0), (0, 1200)])
    gdf = gpd.GeoDataFrame(
        {"osm_id": [1], "highway": ["trunk"], "name": [None], "ref": ["NH1"]}, geometry=[line], crs="EPSG:4326"
    )
    # segment_roads reprojects internally, so build directly in UTM to avoid
    # a real reprojection of a synthetic non-georeferenced line
    gdf_utm_direct = gpd.GeoDataFrame(gdf.drop(columns="geometry"), geometry=[line], crs=utm_crs)
    segments = segment_roads(gdf_utm_direct.set_crs(utm_crs, allow_override=True).to_crs("EPSG:4326"),
                              segment_length_m=500, config=DEFAULT_CONFIG)
    assert len(segments) >= 1
    assert all(segments["osm_id"] == 1)
    assert segments["segment_id"].is_unique


def test_short_line_produces_one_segment_not_zero():
    utm_crs = DEFAULT_CONFIG.dem.target_crs
    line = LineString([(0, 0), (0, 50)])  # much shorter than 500m target
    gdf = gpd.GeoDataFrame({"osm_id": [2], "highway": ["trunk"], "name": [None], "ref": [None]},
                            geometry=[line], crs=utm_crs).to_crs("EPSG:4326")
    segments = segment_roads(gdf, segment_length_m=500, config=DEFAULT_CONFIG)
    assert len(segments) == 1


def test_build_corridors_produces_valid_polygons_with_correct_buffer():
    utm_crs = DEFAULT_CONFIG.dem.target_crs
    line = LineString([(0, 0), (1000, 0)])
    segments = gpd.GeoDataFrame({"segment_id": ["a"]}, geometry=[line], crs=utm_crs)
    corridors = build_corridors(segments, buffer_m=500)

    assert corridors.geometry.iloc[0].is_valid
    assert corridors.geometry.iloc[0].geom_type in ("Polygon", "MultiPolygon")
    # buffering a straight line by 500m: the polygon's width perpendicular
    # to the line should be ~1000m (500m each side)
    bounds = corridors.geometry.iloc[0].bounds
    width = bounds[3] - bounds[1]  # y-extent, perpendicular to the horizontal line
    assert 950 < width < 1050


# --- zonal statistics -----------------------------------------------------


def test_zonal_median_matches_known_values(tmp_path):
    # 10x10 raster, values = row index (0-9), so a polygon covering rows
    # 0-4 has a known, hand-computable median
    arr = np.tile(np.arange(10).reshape(10, 1), (1, 10)).astype("float32")
    transform = from_origin(0, 10, 1, 1)  # 1-unit pixels, origin at (0,10)

    # polygon covering the top 5 rows (rows 0-4, values 0-4 -> median 2)
    polygon = Polygon([(0, 10), (10, 10), (10, 5), (0, 5), (0, 10)])
    median = zonal_median(polygon, arr, transform)
    assert median == pytest.approx(2.0, abs=0.5)


def test_zonal_median_returns_none_outside_raster_bounds():
    arr = np.ones((10, 10), dtype="float32")
    transform = from_origin(0, 10, 1, 1)
    far_away_polygon = Polygon([(1000, 1000), (1010, 1000), (1010, 1010), (1000, 1010)])
    assert zonal_median(far_away_polygon, arr, transform) is None


# --- schema verification ---------------------------------------------------


def test_verify_feature_schema_raises_on_missing_column():
    bundle = {"feature_cols": ["elevation", "slope", "curvature", "distance_to_drainage", "landcover_tree_cover"]}
    features = pd.DataFrame({
        "elevation": [100.0], "slope": [10.0], "curvature": [0.1],
        # distance_to_drainage missing entirely
        "land_cover_class": ["tree_cover"],
    })
    with pytest.raises(AssertionError, match="SCHEMA MISMATCH"):
        verify_feature_schema(features, bundle)


def test_verify_feature_schema_handles_unseen_landcover_class():
    bundle = {"feature_cols": ["elevation", "slope", "curvature", "distance_to_drainage", "landcover_tree_cover"]}
    features = pd.DataFrame({
        "elevation": [100.0], "slope": [10.0], "curvature": [0.1], "distance_to_drainage": [50.0],
        "land_cover_class": ["water"],  # not in bundle's feature_cols
    })
    X = verify_feature_schema(features, bundle)
    assert list(X.columns) == bundle["feature_cols"]
    assert X["landcover_tree_cover"].iloc[0] == 0  # water isn't tree_cover


def test_verify_feature_schema_column_order_matches_bundle():
    bundle = {"feature_cols": ["slope", "elevation", "landcover_water", "curvature", "distance_to_drainage"]}
    features = pd.DataFrame({
        "elevation": [100.0], "slope": [10.0], "curvature": [0.1], "distance_to_drainage": [50.0],
        "land_cover_class": ["water"],
    })
    X = verify_feature_schema(features, bundle)
    assert list(X.columns) == bundle["feature_cols"]


# --- risk tier assignment ---------------------------------------------------


def test_score_to_tier_boundaries():
    assert score_to_tier(0.0, low_cut=0.4, high_cut=0.6) == "low"
    assert score_to_tier(0.39, low_cut=0.4, high_cut=0.6) == "low"
    assert score_to_tier(0.4, low_cut=0.4, high_cut=0.6) == "moderate"
    assert score_to_tier(0.5, low_cut=0.4, high_cut=0.6) == "moderate"
    assert score_to_tier(0.6, low_cut=0.4, high_cut=0.6) == "high"
    assert score_to_tier(1.0, low_cut=0.4, high_cut=0.6) == "high"


# --- backend payload contract ------------------------------------------------


def test_prediction_output_matches_susceptibility_update_schema():
    from app.schemas import SusceptibilityUpdate

    # exactly the shape predict_corridors() attaches to each row
    payload = SusceptibilityUpdate(
        susceptibility_score=0.731, risk_tier="high", model_version="random_forest-extended-v1-20260902"
    )
    assert 0 <= payload.susceptibility_score <= 1
    assert payload.risk_tier in ("low", "moderate", "high")


def test_susceptibility_score_out_of_range_rejected():
    from pydantic import ValidationError

    from app.schemas import SusceptibilityUpdate

    with pytest.raises(ValidationError):
        SusceptibilityUpdate(susceptibility_score=1.5, risk_tier="high", model_version="v1")


# --- integration-style: real model bundle + real DEM (skipped if absent) ---


@pytest.mark.skipif(
    not (DEFAULT_CONFIG.paths.training_dataset_csv.parent.parent / "models" / "susceptibility_model.joblib").exists(),
    reason="trained model artifact not present",
)
def test_real_model_bundle_predict_proba_range():
    from scripts.ml.predict_zone_susceptibility import load_model_bundle

    bundle = load_model_bundle()
    X = pd.DataFrame([{c: 0.5 for c in bundle["feature_cols"]}])
    proba = bundle["pipeline"].predict_proba(X)[:, 1]
    assert (proba >= 0).all() and (proba <= 1).all()


# --- regression test for a real bug caught during backend integration -----


def test_zone_name_is_unique_even_when_multiple_segments_share_a_ref():
    """A real bug, caught by actually running the integration: using `ref`
    alone (e.g. 'NH10') as the zone name collided every segment of the same
    highway into one zone, silently overwriting all but the last-processed
    segment's prediction (3921 segments -> only 1899 distinct zones in the
    database). segment_id must be embedded for uniqueness."""
    from scripts.integrate_zone_predictions import zone_name_for

    same_highway_segments = [
        {"ref": "NH10", "name": None, "segment_id": "44848664_00_000"},
        {"ref": "NH10", "name": None, "segment_id": "44848664_00_001"},
        {"ref": "NH10", "name": None, "segment_id": "44848664_00_002"},
    ]
    names = [zone_name_for(p) for p in same_highway_segments]
    assert len(set(names)) == len(names), f"zone names collided: {names}"
