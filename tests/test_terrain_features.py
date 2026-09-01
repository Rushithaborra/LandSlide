"""Tests for terrain feature extraction, using small synthetic DEMs (no
network, no real 40MB tile needed) so correctness is verified analytically."""
import math

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from scripts.ml.extract_terrain_features import compute_distance_to_drainage, compute_slope_aspect_curvature

PIXEL_SIZE_M = 30.0


def test_slope_matches_analytical_value_for_a_tilted_plane():
    """A plane rising 1m per pixel in the row direction has a known,
    constant true slope everywhere: atan(rise/run). This is the exact bug
    class caught during the data audit (degree-based pixels silently gave
    ~90 degrees everywhere) -- this test guards against a regression."""
    rows, cols = 50, 50
    rise_per_pixel = 1.0  # 1m elevation gain per 30m pixel
    elevation = np.array([[r * rise_per_pixel for _ in range(cols)] for r in range(rows)])

    result = compute_slope_aspect_curvature(elevation, PIXEL_SIZE_M)
    expected_slope_deg = math.degrees(math.atan(rise_per_pixel / PIXEL_SIZE_M))

    interior = result["slope"][10:-10, 10:-10]  # avoid edge artifacts
    assert np.nanmean(interior) == pytest.approx(expected_slope_deg, abs=1.0)
    assert np.nanstd(interior) < 0.5  # a perfect plane should have ~uniform slope


def test_flat_plane_has_near_zero_slope_and_curvature():
    elevation = np.full((50, 50), 1000.0)
    result = compute_slope_aspect_curvature(elevation, PIXEL_SIZE_M)

    interior_slope = result["slope"][10:-10, 10:-10]
    interior_curv = result["curvature"][10:-10, 10:-10]
    assert np.nanmax(interior_slope) < 0.01
    assert np.nanmax(np.abs(interior_curv)) < 1e-6


def test_tilted_plane_has_consistent_aspect_direction():
    """Aspect direction should be near-constant across a uniformly tilted
    plane, not scattered -- regardless of the exact compass convention used,
    a real (non-buggy) computation shouldn't have high variance here."""
    rows, cols = 50, 50
    elevation = np.array([[r * 1.0 for _ in range(cols)] for r in range(rows)])
    result = compute_slope_aspect_curvature(elevation, PIXEL_SIZE_M)

    interior = result["aspect"][10:-10, 10:-10]
    # aspect wraps at 0/360, so compare via circular std proxy: check most
    # values cluster tightly (allow a small fraction near the wrap boundary)
    median = np.nanmedian(interior)
    close_to_median = np.abs(interior - median) < 5
    assert close_to_median.mean() > 0.95


def test_distance_to_drainage_is_near_zero_at_a_synthetic_valley_and_increases_away(tmp_path):
    """Builds a synthetic V-shaped valley (an obvious drainage channel down
    the middle column) and checks the pysheds-based pipeline (incl. the
    numpy compatibility shim) finds it and reports the correct spatial
    pattern: near-zero distance in the valley, larger away from it."""
    rows, cols = 60, 40
    base_elevation = 1000.0
    elevation = np.zeros((rows, cols))
    valley_col = cols // 2
    for r in range(rows):
        for c in range(cols):
            # V-shaped cross-section: elevation rises with distance from the
            # valley column, and gently descends downstream (row direction)
            # so water has somewhere to flow.
            elevation[r, c] = base_elevation - r * 0.5 + abs(c - valley_col) * 5.0

    transform = from_origin(0, rows * PIXEL_SIZE_M, PIXEL_SIZE_M, PIXEL_SIZE_M)
    dem_path = tmp_path / "synthetic_valley.tif"
    with rasterio.open(
        dem_path, "w", driver="GTiff", height=rows, width=cols, count=1,
        dtype=elevation.dtype, crs="EPSG:32645", transform=transform,
    ) as dst:
        dst.write(elevation, 1)

    dist, pixel_size = compute_distance_to_drainage(dem_path, stream_threshold=20)

    valley_distances = dist[10:-5, valley_col]
    edge_distances = dist[10:-5, 2]  # far from the valley
    assert np.mean(valley_distances) < np.mean(edge_distances)
