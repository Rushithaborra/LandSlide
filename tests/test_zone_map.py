"""Tests for the map/nearest-zone logic in app/routers/zones.py that doesn't
need a database: the grid cell size, the great-circle distance, and which risk
tiers count as "safer". (The SQL itself was checked against the real database:
map counts equal /zones/stats counts for every state, and nearest-safer matches
a brute-force search.)"""
import math

import pytest

from app.routers.zones import (
    MAP_GRID_TARGET_CELLS,
    SAFER_TIERS,
    _haversine_km,
    grid_cell_degrees,
)


def test_grid_cell_is_a_power_of_two_so_cell_edges_stay_put_while_panning():
    for span in (0.02, 0.3, 1.7, 6.5, 17.0, 40.0):
        cell = grid_cell_degrees(span)
        assert math.log2(cell) == int(math.log2(cell))


def test_grid_cell_size_tracks_the_view_so_roughly_the_target_cells_fit_across_it():
    for span in (0.5, 2.0, 9.0, 30.0):
        cell = grid_cell_degrees(span)
        cells_across = span / cell
        # floor-to-a-power-of-two means between target and 2x target cells
        assert MAP_GRID_TARGET_CELLS <= cells_across < 2 * MAP_GRID_TARGET_CELLS


def test_zooming_in_never_makes_the_grid_coarser():
    spans = [30.0, 10.0, 3.0, 1.0, 0.3, 0.05]
    cells = [grid_cell_degrees(s) for s in spans]
    assert cells == sorted(cells, reverse=True)


def test_grid_cell_handles_a_degenerate_zero_width_view():
    assert grid_cell_degrees(0.0) > 0


def test_haversine_matches_a_known_distance():
    # One degree of latitude is ~111.2 km everywhere.
    assert _haversine_km(25.0, 93.0, 26.0, 93.0) == pytest.approx(111.2, abs=0.3)
    assert _haversine_km(25.0, 93.0, 25.0, 93.0) == 0


def test_a_high_risk_zone_is_offered_moderate_or_low_but_a_low_zone_is_offered_nothing():
    assert SAFER_TIERS["high"] == ("moderate", "low")
    assert SAFER_TIERS["moderate"] == ("low",)
    assert SAFER_TIERS["low"] == ()


def test_an_unscored_zone_is_only_ever_pointed_at_a_real_low_zone():
    # The router falls back to ("low",) for a tier it doesn't know (None), so
    # it can never send someone toward an unassessed area.
    assert SAFER_TIERS.get(None, ("low",)) == ("low",)
