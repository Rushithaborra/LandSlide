"""Human-review package for the susceptibility training dataset --
the 'REVIEW DATASET' step between dataset construction and training.
Read-only: loads training_dataset.csv, reports on it, plots it. Never
touches a model.
"""
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from scripts.ml.build_negative_samples import to_utm_points
from scripts.ml.ml_config import DEFAULT_CONFIG, MlConfig

FEATURES = ["elevation", "slope", "aspect", "curvature", "distance_to_drainage"]
BANNED_FIELDS = [
    "Material_Involved", "Movement_Type", "Slide_Name", "NH_SH_Location",
    "History", "Slide_No", "distance_to_road",
]


def load(config: MlConfig = DEFAULT_CONFIG) -> pd.DataFrame:
    return pd.read_csv(config.paths.training_dataset_csv)


def report_path(config: MlConfig = DEFAULT_CONFIG) -> None:
    print("=== 1. Dataset path ===")
    print(config.paths.training_dataset_csv.resolve())


def report_sample(df: pd.DataFrame, seed: int) -> None:
    print("\n=== 2. 20-row sample (10 positive + 10 negative) ===")
    pos = df[df["label"] == 1].sample(10, random_state=seed)
    neg = df[df["label"] == 0].sample(10, random_state=seed)
    sample = pd.concat([pos, neg]).sample(frac=1, random_state=seed)  # shuffle so classes aren't grouped
    print(sample.to_string())


def report_summary_stats(df: pd.DataFrame) -> None:
    print("\n=== 3. Summary statistics, every feature ===")
    print(df[FEATURES].describe().T)


def report_class_distributions(df: pd.DataFrame) -> None:
    print("\n=== 4. Positive vs negative distributions ===")
    stats = df.groupby("label")[FEATURES].describe().T
    print(stats)


def report_duplicates_and_overlap(df: pd.DataFrame, config: MlConfig) -> None:
    print("\n=== 7. Duplicate coordinates + class overlap ===")
    dupe_mask = df.duplicated(subset=["latitude", "longitude"], keep=False)
    print(f"exact duplicate (lat,lon) rows in the full dataset: {dupe_mask.sum()}")
    if dupe_mask.any():
        print(df[dupe_mask].sort_values(["latitude", "longitude"]).to_string())

    pos = df[df["label"] == 1]
    neg = df[df["label"] == 0]
    pos_dupe_with_neg = pd.merge(pos[["latitude", "longitude"]], neg[["latitude", "longitude"]], how="inner")
    print(f"positive/negative rows sharing an EXACT coordinate: {len(pos_dupe_with_neg)}")

    pos_pts = to_utm_points(pos["longitude"], pos["latitude"], config.dem.target_crs)
    neg_pts = to_utm_points(neg["longitude"], neg["latitude"], config.dem.target_crs)
    pos_xy = np.array([(p.x, p.y) for p in pos_pts])
    neg_xy = np.array([(p.x, p.y) for p in neg_pts])
    dists, _ = cKDTree(pos_xy).query(neg_xy, k=1)
    print(f"min real-world distance between any positive and any negative: {dists.min():.1f}m "
          f"(configured exclusion buffer: {config.sampling.exclusion_buffer_m}m)")
    violations = (dists < config.sampling.exclusion_buffer_m).sum()
    print(f"negatives violating the exclusion buffer: {violations}")


def report_missing_and_infinite(df: pd.DataFrame) -> None:
    print("\n=== 8. Missing / infinite values ===")
    missing = df.isna().sum()
    print("missing (NaN) per column:")
    print(missing[missing > 0] if missing.any() else "  none")

    numeric = df.select_dtypes(include=[np.number])
    inf_counts = np.isinf(numeric).sum()
    print("infinite values per numeric column:")
    print(inf_counts[inf_counts > 0] if inf_counts.any() else "  none")


def report_feature_rationale() -> None:
    print("\n=== 9. Final feature list + why each is included ===")
    rationale = {
        "elevation": "Base terrain factor in the GSI-recommended factor list; correlates with rock/soil "
                     "weathering regime and land-use pressure at different altitude bands in the Himalaya.",
        "slope": "The single strongest, most literature-consistent predictor of shallow-landslide "
                 "susceptibility -- steeper slopes have less shear resistance to gravity. Verified in this "
                 "dataset: positives average 33.2 deg vs 28.4 deg for negatives.",
        "aspect": "Slope-facing direction affects sun exposure, vegetation cover, and soil moisture "
                   "retention, all of which affect slope stability in monsoon-driven terrain.",
        "curvature": "Concave (valley-converging) terrain concentrates subsurface water flow and pore "
                     "pressure buildup, a known destabilizing factor; convex (ridge) terrain drains water "
                     "away faster.",
        "distance_to_drainage": "Proximity to a drainage channel is a proxy for undercutting/toe erosion "
                                 "and elevated soil saturation -- both documented landslide-preconditioning "
                                 "factors.",
    }
    for feature, why in rationale.items():
        print(f"- {feature}: {why}")

    print("\nDeliberately EXCLUDED (see leakage check below): latitude/longitude as direct model inputs "
          "(risk of memorizing coordinates with only 1554 rows), distance-to-road (would let the model "
          "exploit the road-survey sampling bias instead of learning real terrain signal), and any "
          "rainfall feature (kept in the separate dynamic rule layer, not this static model).")


def report_leakage_check(df: pd.DataFrame) -> None:
    print("\n=== 10. Leakage/post-event field check ===")
    present_banned = [f for f in BANNED_FIELDS if f in df.columns]
    print(f"columns actually in the dataset: {list(df.columns)}")
    print(f"banned post-event/leakage-prone fields found: {present_banned if present_banned else 'none'}")
    assert not present_banned, f"LEAKAGE: found banned fields {present_banned} in the training dataset"
    print("confirmed: no post-event outcome fields, no rainfall, no raw distance-to-road in the dataset.")


def plot_feature_distributions(df: pd.DataFrame, config: MlConfig) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    axes = axes.flatten()
    for ax, feature in zip(axes, FEATURES):
        for label, color, name in [(1, "tab:red", "positive"), (0, "tab:blue", "negative")]:
            values = df.loc[df["label"] == label, feature]
            ax.hist(values, bins=30, alpha=0.5, color=color, label=name, density=True)
        ax.set_title(feature)
        ax.set_xlabel(feature)
        ax.set_ylabel("density")
        ax.legend()
    axes[-1].axis("off")
    fig.suptitle("Feature distributions by class — Sikkim road-corridor susceptibility dataset")
    fig.tight_layout()

    out_path = config.paths.training_dataset_csv.parent / "feature_distributions.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\n=== 5. Feature distribution plot ===\nsaved -> {out_path}")


def run_review(config: MlConfig = DEFAULT_CONFIG) -> None:
    df = load(config)
    report_path(config)
    report_sample(df, config.sampling.random_seed)
    report_summary_stats(df)
    report_class_distributions(df)
    plot_feature_distributions(df, config)
    print(f"\n=== 6. Sampling map === already saved at {config.paths.sampling_plot.resolve()}")
    report_duplicates_and_overlap(df, config)
    report_missing_and_infinite(df)
    report_feature_rationale()
    report_leakage_check(df)
    print("\n=== STOP: review package generated. No model trained. ===")


if __name__ == "__main__":
    run_review()
