"""Orchestrates the full dataset build: positives (GSI) + negatives (road-
corridor sampling) + terrain features (DEM) -> one CSV.

Stops after writing the dataset and a review summary/plot. Does NOT train
any model -- that's a separate, later, explicitly-approved step.

Leakage-flagged GSI columns (Material_Involved, Movement_Type, free-text
Slide_Name/NH_SH_Location) are dropped here, not carried into the feature
set -- see the data-audit report for why each is excluded.
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from shapely.geometry import LineString

from scripts.ml.build_negative_samples import build_negative_samples, to_utm_points
from scripts.ml.extract_terrain_features import build_feature_stack, sample_at_points
from scripts.ml.fetch_dem import download_tile, reproject_to_utm
from scripts.ml.fetch_osm_roads import load_roads
from scripts.ml.ml_config import DEFAULT_CONFIG, MlConfig


def load_positives(config: MlConfig) -> pd.DataFrame:
    df = pd.read_csv(config.paths.gsi_sikkim_csv)
    df = df.rename(columns={"Latitude": "latitude", "Longitude": "longitude", "District": "district"})
    df["label"] = 1
    # Leakage columns dropped here -- never enter the feature set.
    return df[["latitude", "longitude", "district", "label"]].copy()


def min_distance_between_classes(positives_df: pd.DataFrame, negatives_df: pd.DataFrame, target_crs: str) -> float:
    pos_pts = to_utm_points(positives_df["longitude"], positives_df["latitude"], target_crs)
    neg_pts = to_utm_points(negatives_df["longitude"], negatives_df["latitude"], target_crs)
    pos_xy = np.array([(p.x, p.y) for p in pos_pts])
    neg_xy = np.array([(p.x, p.y) for p in neg_pts])
    tree = cKDTree(pos_xy)
    dists, _ = tree.query(neg_xy, k=1)
    return float(dists.min())


def print_summary(positives_df: pd.DataFrame, negatives_df: pd.DataFrame, config: MlConfig) -> None:
    print("\n=== Dataset summary ===")
    print(f"positive count: {len(positives_df)}")
    print(f"negative count: {len(negatives_df)}")
    print(f"ratio (neg/pos): {len(negatives_df) / len(positives_df):.2f} (target {config.sampling.ratio})")

    print("\ndistrict distribution (positive vs negative):")
    dist = pd.DataFrame(
        {"positive": positives_df["district"].value_counts(), "negative": negatives_df["district"].value_counts()}
    ).fillna(0).astype(int)
    print(dist)

    min_dist = min_distance_between_classes(positives_df, negatives_df, config.dem.target_crs)
    print(f"\nmin distance between any positive and any negative: {min_dist:.1f}m "
          f"(exclusion buffer was {config.sampling.exclusion_buffer_m}m)")

    print("\nsample of generated negatives:")
    print(negatives_df.sample(min(10, len(negatives_df)), random_state=config.sampling.random_seed).to_string())


def plot_sampling(positives_df: pd.DataFrame, negatives_df: pd.DataFrame, roads_gdf, config: MlConfig) -> None:
    fig, ax = plt.subplots(figsize=(9, 9))
    roads_gdf.plot(ax=ax, color="lightgray", linewidth=0.5, zorder=1)
    ax.scatter(negatives_df["longitude"], negatives_df["latitude"], s=8, c="tab:blue", label="negative (sampled)", zorder=2)
    ax.scatter(positives_df["longitude"], positives_df["latitude"], s=10, c="tab:red", label="positive (GSI landslide)", zorder=3)
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    ax.set_title("Road-corridor susceptibility sampling — Sikkim pilot")
    ax.legend(loc="upper right")
    ax.set_aspect("equal")
    config.paths.sampling_plot.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(config.paths.sampling_plot, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\nsampling map saved -> {config.paths.sampling_plot}")


def build_dataset(config: MlConfig = DEFAULT_CONFIG) -> pd.DataFrame:
    positives_df = load_positives(config)
    roads_gdf = load_roads(config)
    negatives_df = build_negative_samples(
        pd.read_csv(config.paths.gsi_sikkim_csv), config, roads_gdf=roads_gdf
    )

    print_summary(positives_df, negatives_df, config)
    plot_sampling(positives_df, negatives_df, roads_gdf, config)

    tile_paths = [download_tile(t, config) for t in config.dem.tile_ids]
    if not config.paths.dem_utm_path.exists():
        reproject_to_utm(tile_paths, config)
    feature_stack = build_feature_stack(config.paths.dem_utm_path, config)

    combined = pd.concat([positives_df, negatives_df], ignore_index=True)
    features = sample_at_points(feature_stack, combined["longitude"].values, combined["latitude"].values)

    out_of_bounds = (~features["in_bounds"]).sum()
    if out_of_bounds:
        print(f"WARNING: {out_of_bounds} points fell outside the DEM tile and were dropped.")

    dataset = pd.concat([combined, features], axis=1)
    dataset = dataset[dataset["in_bounds"]].drop(columns=["in_bounds"]).reset_index(drop=True)

    config.paths.training_dataset_csv.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(config.paths.training_dataset_csv, index=False)
    print(f"\nfinal dataset ({len(dataset)} rows) -> {config.paths.training_dataset_csv}")
    print("columns:", list(dataset.columns))
    print("\nNOTE: dataset written. No model has been trained. Review before proceeding.")
    return dataset


if __name__ == "__main__":
    build_dataset()
