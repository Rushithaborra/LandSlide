"""Spatial block cross-validation -- the split strategy for the susceptibility
model. A naive random point split is not defensible here: our own data
audits this session showed strong small-scale spatial clustering (positives
median ~7-10m from a road, negative sampling within a few hundred meters of
positives in places) so a random split would very likely put near-identical
neighboring points in both train and test, inflating apparent performance
without the model having learned anything it couldn't already see.

Method: assign every point to a grid cell (in UTM meters, not degrees, so
cell size is physically meaningful), then assign whole cells to folds --
never split a cell's points across folds. This guarantees train and test
points are separated by at least the cell size wherever they're adjacent,
not just "different by chance."

Cell size: 2km. Chosen because it's an order of magnitude larger than the
200m positive/negative exclusion buffer already used in sampling, and larger
than the scale terrain features (slope, curvature) typically vary over in
this terrain (tens to a few hundred meters) -- see docs/duplicate_and_bias_audit.md
for the related distance-to-road analysis this builds on.
"""
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from scripts.ml.build_negative_samples import to_utm_points
from scripts.ml.ml_config import DEFAULT_CONFIG, MlConfig

CELL_SIZE_M = 2000.0


def assign_spatial_blocks(df: pd.DataFrame, config: MlConfig = DEFAULT_CONFIG, cell_size_m: float = CELL_SIZE_M) -> pd.Series:
    pts = to_utm_points(df["longitude"], df["latitude"], config.dem.target_crs)
    xs = np.array([p.x for p in pts])
    ys = np.array([p.y for p in pts])
    col = np.floor(xs / cell_size_m).astype(int)
    row = np.floor(ys / cell_size_m).astype(int)
    return pd.Series([f"{r}_{c}" for r, c in zip(row, col)], index=df.index, name="block_id")


def assign_folds(block_ids: pd.Series, n_folds: int = 5, seed: int = 42) -> pd.Series:
    """Randomly assigns whole blocks to folds (not individual points), so a
    block's points are never split across train and test."""
    unique_blocks = sorted(block_ids.unique())
    rng = np.random.default_rng(seed)
    block_fold = {b: f for b, f in zip(unique_blocks, rng.integers(0, n_folds, size=len(unique_blocks)))}
    return block_ids.map(block_fold).rename("fold")


def _to_xy(df: pd.DataFrame, mask: pd.Series, config: MlConfig) -> np.ndarray:
    pts = to_utm_points(df.loc[mask, "longitude"], df.loc[mask, "latitude"], config.dem.target_crs)
    return np.array([(p.x, p.y) for p in pts])


def min_train_test_distance(df: pd.DataFrame, train_mask: pd.Series, test_mask: pd.Series,
                             config: MlConfig = DEFAULT_CONFIG) -> float:
    train_xy = _to_xy(df, train_mask, config)
    test_xy = _to_xy(df, test_mask, config)
    dists, _ = cKDTree(train_xy).query(test_xy, k=1)
    return float(dists.min())


# Buffer distance: matches the 200m positive/negative exclusion buffer
# already established in the sampling design (build_negative_samples.py) --
# reusing the same scale keeps the "what counts as too close" definition
# consistent across the whole pipeline rather than picking a new number.
BUFFER_M = 200.0


def buffer_train_mask(df: pd.DataFrame, train_mask: pd.Series, test_mask: pd.Series,
                       buffer_m: float = BUFFER_M, config: MlConfig = DEFAULT_CONFIG) -> pd.Series:
    """Grid blocking alone still allows train/test points to sit right next
    to each other across a cell boundary (measured: 56-69m on this dataset,
    inside the 200m buffer we already use elsewhere). This drops TRAIN
    points within buffer_m of any TEST point -- shrinks training data near
    the boundary rather than the held-out test set, so test performance
    still reflects the full, representative held-out fold."""
    train_idx = df.index[train_mask]
    train_xy = _to_xy(df, train_mask, config)
    test_xy = _to_xy(df, test_mask, config)
    dists, _ = cKDTree(test_xy).query(train_xy, k=1)
    keep = dists >= buffer_m
    buffered_mask = pd.Series(False, index=df.index)
    buffered_mask.loc[train_idx[keep]] = True
    return buffered_mask


def summarize_folds(df: pd.DataFrame, folds: pd.Series, config: MlConfig = DEFAULT_CONFIG) -> None:
    print(f"blocks/folds summary (cell size {CELL_SIZE_M/1000:.0f}km, buffer {BUFFER_M:.0f}m):")
    for fold in sorted(folds.unique()):
        mask = folds == fold
        pos = (df.loc[mask, "label"] == 1).sum()
        neg = (df.loc[mask, "label"] == 0).sum()
        print(f"  fold {fold} (test): {mask.sum()} points ({pos} pos / {neg} neg)")

    for fold in sorted(folds.unique()):
        test_mask = folds == fold
        raw_train_mask = ~test_mask
        d_before = min_train_test_distance(df, raw_train_mask, test_mask, config)

        buffered_train_mask = buffer_train_mask(df, raw_train_mask, test_mask, config=config)
        d_after = min_train_test_distance(df, buffered_train_mask, test_mask, config)
        dropped = raw_train_mask.sum() - buffered_train_mask.sum()
        print(f"  fold {fold}: unbuffered min train-test dist = {d_before:.1f}m -> "
              f"after {BUFFER_M:.0f}m buffer = {d_after:.1f}m "
              f"({dropped} train points dropped near the boundary, "
              f"{buffered_train_mask.sum()} train points remain)")
