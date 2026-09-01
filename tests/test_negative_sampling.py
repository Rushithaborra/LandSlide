"""Tests for the road-corridor negative-sampling method. Uses synthetic
geometry (no network calls, no real DEM/roads needed) so these run fast and
deterministically."""
import dataclasses

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString, Point

from scripts.ml.build_negative_samples import (
    build_district_region,
    build_exclusion_zone,
    build_negative_samples,
    build_road_corridor,
    build_sampling_region,
    rejection_sample_points,
    to_utm_points,
)
from scripts.ml.ml_config import DEFAULT_CONFIG, MlConfig, NegativeSamplingConfig

TARGET_CRS = DEFAULT_CONFIG.dem.target_crs


@pytest.fixture
def synthetic_positives() -> pd.DataFrame:
    # District A: 5 points along a short east-west line near 27.30N, 88.50E
    a_lons = np.linspace(88.495, 88.505, 5)
    a_lats = [27.300] * 5
    # District B: 3 points along a short line near 27.35N, 88.60E
    b_lons = np.linspace(88.598, 88.604, 3)
    b_lats = [27.350] * 3

    return pd.DataFrame({
        "Latitude": list(a_lats) + list(b_lats),
        "Longitude": list(a_lons) + list(b_lons),
        "District": ["DistrictA"] * 5 + ["DistrictB"] * 3,
    })


@pytest.fixture
def synthetic_roads() -> gpd.GeoDataFrame:
    road_a = LineString([(88.49, 27.300), (88.51, 27.300)])
    road_b = LineString([(88.595, 27.350), (88.61, 27.350)])
    return gpd.GeoDataFrame(geometry=[road_a, road_b], crs="EPSG:4326")


@pytest.fixture
def test_config() -> MlConfig:
    sampling = NegativeSamplingConfig(
        corridor_buffer_m=300.0,
        exclusion_buffer_m=50.0,
        district_hull_buffer_m=1000.0,
        ratio=1.0,
        random_seed=123,
    )
    return dataclasses.replace(DEFAULT_CONFIG, sampling=sampling)


def test_no_negative_within_exclusion_buffer_of_any_positive(synthetic_positives, synthetic_roads, test_config):
    negatives = build_negative_samples(synthetic_positives, test_config, roads_gdf=synthetic_roads)
    assert len(negatives) > 0, "sanity: the synthetic corridor should yield at least some negatives"

    pos_points = to_utm_points(synthetic_positives["Longitude"], synthetic_positives["Latitude"], TARGET_CRS)
    neg_points = to_utm_points(negatives["longitude"], negatives["latitude"], TARGET_CRS)

    for neg in neg_points:
        min_dist = min(neg.distance(pos) for pos in pos_points)
        assert min_dist >= test_config.sampling.exclusion_buffer_m, (
            f"negative point at distance {min_dist:.1f}m from nearest positive, "
            f"violates exclusion buffer of {test_config.sampling.exclusion_buffer_m}m"
        )


def test_reproducible_with_same_seed(synthetic_positives, synthetic_roads, test_config):
    run1 = build_negative_samples(synthetic_positives, test_config, roads_gdf=synthetic_roads)
    run2 = build_negative_samples(synthetic_positives, test_config, roads_gdf=synthetic_roads)
    pd.testing.assert_frame_equal(run1.reset_index(drop=True), run2.reset_index(drop=True))


def test_different_seed_gives_different_points(synthetic_positives, synthetic_roads, test_config):
    other_config = dataclasses.replace(
        test_config, sampling=dataclasses.replace(test_config.sampling, random_seed=999)
    )
    run1 = build_negative_samples(synthetic_positives, test_config, roads_gdf=synthetic_roads)
    run2 = build_negative_samples(synthetic_positives, other_config, roads_gdf=synthetic_roads)
    assert not run1["latitude"].equals(run2["latitude"]), "different seeds should not produce identical samples"


def test_district_proportions_preserved(synthetic_positives, synthetic_roads, test_config):
    negatives = build_negative_samples(synthetic_positives, test_config, roads_gdf=synthetic_roads)
    pos_counts = synthetic_positives["District"].value_counts()
    neg_counts = negatives["district"].value_counts()

    for district, pos_n in pos_counts.items():
        expected = round(pos_n * test_config.sampling.ratio)
        actual = neg_counts.get(district, 0)
        assert actual == expected, (
            f"{district}: expected {expected} negatives ({pos_n} positives x ratio "
            f"{test_config.sampling.ratio}), got {actual}"
        )


def test_rejection_sample_points_fall_inside_polygon():
    polygon = Point(0, 0).buffer(100)  # simple 100m-radius disc
    rng = np.random.default_rng(1)
    points = rejection_sample_points(polygon, 50, rng)
    assert len(points) == 50
    assert all(polygon.contains(p) for p in points)


def test_rejection_sample_returns_fewer_when_region_too_small():
    # A thin sliver: bounding box is large relative to actual polygon area,
    # so most random points in the bbox land outside it -- unlike a disc
    # (sampled within its own tight bbox), this makes rejection sampling
    # genuinely inefficient and lets max_attempts run out before n is met.
    sliver = LineString([(0, 0), (1000, 1)]).buffer(0.5)
    rng = np.random.default_rng(1)
    points = rejection_sample_points(sliver, 1000, rng, max_attempts=500)
    assert len(points) < 1000  # must not hang or raise; graceful shortfall


def test_build_sampling_region_excludes_positive_buffers():
    corridor = Point(0, 0).buffer(500)
    positive = Point(0, 0)
    exclusion = build_exclusion_zone([positive], exclusion_m=100)
    region = build_sampling_region(corridor, exclusion)
    assert not region.contains(Point(10, 10))  # inside the 100m exclusion disc
    assert region.contains(Point(200, 0))  # outside exclusion, inside corridor


def test_build_district_region_restricts_to_district_points():
    corridor = Point(0, 0).buffer(5000)
    near_district_point = Point(100, 100)
    far_point_outside_hull = Point(4000, 4000)
    region = build_district_region(corridor, [near_district_point], hull_buffer_m=500)
    assert region.contains(Point(150, 100))  # near the district point
    assert not region.contains(far_point_outside_hull)  # far from this district's own points
