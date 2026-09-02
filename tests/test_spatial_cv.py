"""Tests for the spatial block CV buffering logic -- the core mechanism
behind the "spatially defensible split" claim in the model training report.
Synthetic points, no real dataset/DEM needed."""
import numpy as np
import pandas as pd
import pytest

from scripts.ml.spatial_cv import assign_folds, assign_spatial_blocks, buffer_train_mask, min_train_test_distance


@pytest.fixture
def synthetic_grid_df() -> pd.DataFrame:
    """A dense regular grid of points around Gangtok (~50m spacing in
    degrees at this latitude) so many points sit near any given fold
    boundary -- a harder case than sparse data for the buffer to handle."""
    lats = np.linspace(27.30, 27.35, 40)
    lons = np.linspace(88.55, 88.60, 40)
    grid_lat, grid_lon = np.meshgrid(lats, lons)
    return pd.DataFrame({
        "latitude": grid_lat.ravel(), "longitude": grid_lon.ravel(),
        "label": np.random.default_rng(0).integers(0, 2, grid_lat.size),
    })


def test_buffered_split_achieves_minimum_separation(synthetic_grid_df):
    df = synthetic_grid_df
    blocks = assign_spatial_blocks(df, cell_size_m=1000)
    folds = assign_folds(blocks, n_folds=5, seed=1)

    buffer_m = 200.0
    for fold in sorted(folds.unique()):
        test_mask = folds == fold
        raw_train_mask = ~test_mask
        buffered_train = buffer_train_mask(df, raw_train_mask, test_mask, buffer_m=buffer_m)
        if buffered_train.sum() == 0 or test_mask.sum() == 0:
            continue
        d = min_train_test_distance(df, buffered_train, test_mask)
        assert d >= buffer_m - 1e-6, f"fold {fold}: min distance {d:.1f}m is below the {buffer_m}m buffer"


def test_buffering_never_removes_test_points(synthetic_grid_df):
    df = synthetic_grid_df
    blocks = assign_spatial_blocks(df, cell_size_m=1000)
    folds = assign_folds(blocks, n_folds=5, seed=1)

    for fold in sorted(folds.unique()):
        test_mask = folds == fold
        raw_train_mask = ~test_mask
        buffered_train = buffer_train_mask(df, raw_train_mask, test_mask)
        # buffering only ever removes TRAIN points, never touches the test set
        assert not (buffered_train & test_mask).any()


def test_buffering_only_shrinks_training_set(synthetic_grid_df):
    df = synthetic_grid_df
    blocks = assign_spatial_blocks(df, cell_size_m=1000)
    folds = assign_folds(blocks, n_folds=5, seed=1)

    for fold in sorted(folds.unique()):
        test_mask = folds == fold
        raw_train_mask = ~test_mask
        buffered_train = buffer_train_mask(df, raw_train_mask, test_mask)
        assert buffered_train.sum() <= raw_train_mask.sum()
        assert (buffered_train <= raw_train_mask).all()  # never adds a point raw didn't have


def test_a_single_far_away_point_is_never_buffered_out():
    """A point 10km from everything else should never be dropped by a 200m
    buffer -- sanity check that buffering is distance-based, not arbitrary."""
    df = pd.DataFrame({
        "latitude": [27.30, 27.30, 27.30, 27.40],  # last point far away
        "longitude": [88.55, 88.5505, 88.551, 88.70],
        "label": [1, 0, 1, 0],
    })
    test_mask = pd.Series([True, True, False, False])
    train_mask = pd.Series([False, False, True, True])
    buffered = buffer_train_mask(df, train_mask, test_mask, buffer_m=200.0)
    assert buffered.iloc[3], "the far-away point should survive buffering regardless of the near points"
