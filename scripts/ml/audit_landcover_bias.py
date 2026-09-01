"""Investigates whether land_cover_class (specifically the built_up signal)
is genuine terrain signal or a proxy for the known road-survey sampling
bias (positives are GSI road-cut inspections, median ~7m from a road;
negatives are spread across a wider corridor).

distance_to_road is computed here PURELY as a diagnostic -- it is never
added to training_dataset.csv or used as a model feature. Using it as a
feature would leak the sampling process itself into the model (see the
feature-suitability report); using it here to CHECK for that leakage is
the opposite move and is exactly what this script is for.
"""
import numpy as np
import pandas as pd
from scipy import stats
from scipy.spatial import cKDTree
from shapely.ops import transform as shp_transform
import pyproj

from scripts.ml.build_negative_samples import to_utm_points
from scripts.ml.fetch_osm_roads import load_roads
from scripts.ml.ml_config import DEFAULT_CONFIG, MlConfig


def compute_distance_to_road(df: pd.DataFrame, config: MlConfig = DEFAULT_CONFIG) -> np.ndarray:
    roads_gdf = load_roads(config)
    transformer = pyproj.Transformer.from_crs("EPSG:4326", config.dem.target_crs, always_xy=True)
    roads_utm = [shp_transform(transformer.transform, geom) for geom in roads_gdf.geometry]

    # Sample each road line into points for a fast KD-tree nearest-neighbor
    # distance (good enough for a diagnostic -- not claiming survey-grade
    # precision, just relative comparison between classes).
    road_points = []
    for line in roads_utm:
        n = max(int(line.length // 20), 2)  # a point every ~20m
        road_points.extend(line.interpolate(i / n, normalized=True) for i in range(n + 1))
    road_xy = np.array([(p.x, p.y) for p in road_points])
    tree = cKDTree(road_xy)

    pts = to_utm_points(df["longitude"], df["latitude"], config.dem.target_crs)
    pts_xy = np.array([(p.x, p.y) for p in pts])
    dists, _ = tree.query(pts_xy, k=1)
    return dists


def run_audit(config: MlConfig = DEFAULT_CONFIG) -> pd.DataFrame:
    df = pd.read_csv(config.paths.training_dataset_csv)
    df["distance_to_road_m"] = compute_distance_to_road(df, config)

    print("=== 1. distance-to-road by class (positive vs negative) ===")
    print(df.groupby("label")["distance_to_road_m"].describe())

    print("\n=== 2. distance-to-road by land_cover_class (whole dataset, both labels) ===")
    print(df.groupby("land_cover_class")["distance_to_road_m"].describe()[["count", "mean", "50%"]])

    print("\n=== 3. distance-to-road by land_cover_class, WITHIN positives only ===")
    print(df[df["label"] == 1].groupby("land_cover_class")["distance_to_road_m"].describe()[["count", "mean", "50%"]])

    print("\n=== 4. distance-to-road by land_cover_class, WITHIN negatives only ===")
    print(df[df["label"] == 0].groupby("land_cover_class")["distance_to_road_m"].describe()[["count", "mean", "50%"]])

    is_built_up = df["landcover_built_up"].astype(bool)
    print("\n=== 5. correlation: is_built_up vs distance_to_road (whole dataset) ===")
    r, p = stats.pointbiserialr(is_built_up, df["distance_to_road_m"])
    print(f"point-biserial r = {r:.3f}, p = {p:.2e}  (negative r = built_up points are CLOSER to roads)")

    print("\n=== 6. correlation: is_built_up vs label (whole dataset) ===")
    r2, p2 = stats.pointbiserialr(is_built_up, df["label"])
    print(f"point-biserial r = {r2:.3f}, p = {p2:.2e}")

    print("\n=== 7. stratified check: land-cover distribution by label, WITHIN distance-to-road bins ===")
    bins = [0, 20, 50, 150, 500, np.inf]
    labels_bins = ["0-20m", "20-50m", "50-150m", "150-500m", "500m+"]
    df["road_dist_bin"] = pd.cut(df["distance_to_road_m"], bins=bins, labels=labels_bins)
    for b in labels_bins:
        subset = df[df["road_dist_bin"] == b]
        if len(subset) == 0:
            continue
        pos = subset[subset["label"] == 1]
        neg = subset[subset["label"] == 0]
        pos_built_pct = pos["landcover_built_up"].mean() * 100 if len(pos) else float("nan")
        neg_built_pct = neg["landcover_built_up"].mean() * 100 if len(neg) else float("nan")
        print(f"  {b:>10s}: n_pos={len(pos):4d} built_up%={pos_built_pct:5.1f}   "
              f"n_neg={len(neg):4d} built_up%={neg_built_pct:5.1f}")

    print("\n=== 8. within the SAME distance-to-road bin, does label still predict built_up? ===")
    print("(if built_up% stays higher for positives than negatives even in the same distance")
    print(" bin, that's evidence of a real effect beyond mere road proximity; if it converges,")
    print(" built_up is likely just tracking road proximity, which itself tracks the label")
    print(" only because of how positives were surveyed.)")

    plot_stratified_built_up(df, labels_bins, config)
    return df


def plot_stratified_built_up(df: pd.DataFrame, dist_bins: list[str], config: MlConfig) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 6))
    x = np.arange(len(dist_bins))
    width = 0.35
    pos_pct, neg_pct, pos_n, neg_n = [], [], [], []
    for b in dist_bins:
        subset = df[df["road_dist_bin"] == b]
        pos = subset[subset["label"] == 1]
        neg = subset[subset["label"] == 0]
        pos_pct.append(pos["landcover_built_up"].mean() * 100 if len(pos) else 0)
        neg_pct.append(neg["landcover_built_up"].mean() * 100 if len(neg) else 0)
        pos_n.append(len(pos))
        neg_n.append(len(neg))

    ax.bar(x - width / 2, pos_pct, width, color="tab:red", alpha=0.75, label="positive")
    ax.bar(x + width / 2, neg_pct, width, color="tab:blue", alpha=0.75, label="negative")
    for i, (pn, nn) in enumerate(zip(pos_n, neg_n)):
        ax.text(i - width / 2, pos_pct[i] + 0.3, f"n={pn}", ha="center", fontsize=8)
        ax.text(i + width / 2, neg_pct[i] + 0.3, f"n={nn}", ha="center", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(dist_bins)
    ax.set_xlabel("distance to nearest road")
    ax.set_ylabel("% of class that is built_up land cover")
    ax.set_title("Built-up land cover by class, stratified by road distance\n"
                 "(if bars converge at each distance -> built_up is just a road-proximity proxy)")
    ax.legend()
    fig.tight_layout()

    out_path = config.paths.training_dataset_csv.parent / "landcover_bias_audit.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\nplot saved -> {out_path}")


if __name__ == "__main__":
    run_audit()
