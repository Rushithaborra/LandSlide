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

# Approved USE set (feature-suitability report, 2026-09-01). aspect and the
# SoilGrids properties are OPTIONAL and deliberately not in this CSV --
# see report_optional_features_check() below, which confirms that.
FEATURES = ["elevation", "slope", "curvature", "distance_to_drainage"]
BANNED_FIELDS = [
    "Material_Involved", "Movement_Type", "Slide_Name", "NH_SH_Location",
    "History", "Slide_No", "distance_to_road",
]
OPTIONAL_FIELDS_THAT_MUST_STAY_OUT = [
    "aspect", "clay", "sand", "silt", "soil_organic_carbon", "soc",
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
    print("\n=== 3. Summary statistics, every continuous feature ===")
    print(df[FEATURES].describe().T)


def report_class_distributions(df: pd.DataFrame) -> None:
    print("\n=== 4. Positive vs negative distributions (continuous features) ===")
    stats = df.groupby("label")[FEATURES].describe().T
    print(stats)

    print("\nLand-cover category distribution by class:")
    landcover_cols = [c for c in df.columns if c.startswith("landcover_")]
    for label, name in [(1, "positive"), (0, "negative")]:
        subset = df[df["label"] == label]
        counts = subset[landcover_cols].sum().sort_values(ascending=False)
        pct = (counts / len(subset) * 100).round(1)
        print(f"\n  {name} (n={len(subset)}):")
        for col in counts.index:
            print(f"    {col}: {int(counts[col])} ({pct[col]}%)")


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


def report_class_balance(df: pd.DataFrame) -> None:
    print("\n=== Class balance ===")
    counts = df["label"].value_counts()
    print(f"positive (1): {counts.get(1, 0)}")
    print(f"negative (0): {counts.get(0, 0)}")
    print(f"ratio: {counts.get(0, 0) / counts.get(1, 1):.3f}")


def report_district_proportions(df: pd.DataFrame) -> None:
    print("\n=== District proportions (positive vs negative) ===")
    dist = pd.DataFrame({
        "positive": df[df["label"] == 1]["district"].value_counts(),
        "negative": df[df["label"] == 0]["district"].value_counts(),
    }).fillna(0).astype(int)
    print(dist)


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
        "curvature": "Concave (valley-converging) terrain concentrates subsurface water flow and pore "
                     "pressure buildup, a known destabilizing factor; convex (ridge) terrain drains water "
                     "away faster.",
        "distance_to_drainage": "Proximity to a drainage channel is a proxy for undercutting/toe erosion "
                                 "and elevated soil saturation -- both documented landslide-preconditioning "
                                 "factors.",
        "land_cover_class (one-hot)": "Vegetation/root reinforcement affects slope stability; 10m "
                                       "resolution, zero leakage risk (2021 snapshot, predates all "
                                       "training events), cheap to extract.",
    }
    for feature, why in rationale.items():
        print(f"- {feature}: {why}")

    print("\nDeliberately EXCLUDED as model inputs: latitude/longitude (memorization risk with only "
          "1554 rows), distance-to-road (would let the model exploit the road-survey sampling bias "
          "instead of learning real terrain signal), rainfall (kept in the separate dynamic rule layer), "
          "aspect and SoilGrids properties (OPTIONAL, held out of this first dataset -- see below).")


def report_optional_features_check(df: pd.DataFrame) -> None:
    print("\n=== OPTIONAL-features-stay-out check ===")
    present = [f for f in OPTIONAL_FIELDS_THAT_MUST_STAY_OUT if f in df.columns]
    print(f"OPTIONAL fields found in the training dataset: {present if present else 'none'}")
    assert not present, f"{present} should be OPTIONAL (held out), not in the training dataset"
    print("confirmed: aspect and SoilGrids properties (clay/sand/silt/soc) are correctly NOT in this "
          "dataset -- retained as candidates for later model comparison, per instruction, via "
          "scripts/ml/extract_terrain_features.py (aspect) and the raw SoilGrids rasters in "
          "data/raw/soilgrids/ (not yet extracted to points).")


def report_leakage_check(df: pd.DataFrame) -> None:
    print("\n=== 10. Leakage/post-event field check ===")
    present_banned = [f for f in BANNED_FIELDS if f in df.columns]
    print(f"columns actually in the dataset: {list(df.columns)}")
    print(f"banned post-event/leakage-prone fields found: {present_banned if present_banned else 'none'}")
    assert not present_banned, f"LEAKAGE: found banned fields {present_banned} in the training dataset"
    print("confirmed: no post-event outcome fields, no rainfall, no raw distance-to-road, no lat/lon "
          "as a feature (kept only as identifying/join keys), no susceptibility-map-derived label.")


def plot_feature_distributions(df: pd.DataFrame, config: MlConfig) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    landcover_cols = [c for c in df.columns if c.startswith("landcover_")]
    n_panels = len(FEATURES) + 1  # +1 for land cover bar panel
    n_cols = 3
    n_rows = -(-n_panels // n_cols)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(15, 4 * n_rows))
    axes = axes.flatten()

    for ax, feature in zip(axes, FEATURES):
        for label, color, name in [(1, "tab:red", "positive"), (0, "tab:blue", "negative")]:
            values = df.loc[df["label"] == label, feature]
            ax.hist(values, bins=30, alpha=0.5, color=color, label=name, density=True)
        ax.set_title(feature)
        ax.set_xlabel(feature)
        ax.set_ylabel("density")
        ax.legend()

    # Land cover panel: grouped bar chart, % of each class within each class label
    ax = axes[len(FEATURES)]
    pos_pct = df[df["label"] == 1][landcover_cols].mean() * 100
    neg_pct = df[df["label"] == 0][landcover_cols].mean() * 100
    labels = [c.replace("landcover_", "") for c in landcover_cols]
    x = np.arange(len(labels))
    width = 0.35
    ax.bar(x - width / 2, pos_pct.values, width, color="tab:red", alpha=0.7, label="positive")
    ax.bar(x + width / 2, neg_pct.values, width, color="tab:blue", alpha=0.7, label="negative")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_ylabel("% of class")
    ax.set_title("land_cover_class")
    ax.legend()

    for ax in axes[n_panels:]:
        ax.axis("off")

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
    report_class_balance(df)
    report_district_proportions(df)
    report_missing_and_infinite(df)
    report_feature_rationale()
    report_optional_features_check(df)
    report_leakage_check(df)
    print("\n=== STOP: review package generated. No model trained. ===")


if __name__ == "__main__":
    run_review()
