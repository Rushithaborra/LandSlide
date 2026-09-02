"""Applies the trained susceptibility model to produce zone-ready
predictions (susceptibility_score, risk_tier, model_version) -- the exact
shape PUT /zones/{id}/susceptibility expects.

HONEST GAP: no real Sikkim pilot zone polygons exist in the database yet
(scripts/seed_zone.py has only ever been run with the documented Gulf-of-
Guinea placeholder -- see config/pilot_zone.example.geojson). This script
cannot produce real zone predictions because there are no real zones to
predict for. What it does instead:

1. Demonstrates the full prediction pipeline (DEM + land-cover feature
   extraction -> model -> score/tier) on the training dataset's own point
   locations, as a readiness proof, clearly labeled as such.
2. Provides predict_at_points(), the exact function real zone centroids
   would be run through the moment Data/GIS lead's boundary exists.

Do not present the output of this script as real Sikkim zone predictions.
"""
import joblib
import numpy as np
import pandas as pd

from scripts.ml.extract_landcover import one_hot_encode, sample_land_cover
from scripts.ml.extract_terrain_features import build_feature_stack, sample_at_points
from scripts.ml.ml_config import DEFAULT_CONFIG, MlConfig
from scripts.ml.train_susceptibility_model import ARTIFACT_DIR, score_to_tier


def load_model_bundle(path=None):
    path = path or (ARTIFACT_DIR / "susceptibility_model.joblib")
    bundle = joblib.load(path)
    report = pd.read_json(ARTIFACT_DIR / "validation_report.json", typ="series")
    bundle["low_cut"] = report["risk_tier_thresholds"]["low_max"]
    bundle["high_cut"] = report["risk_tier_thresholds"]["moderate_max"]
    return bundle


def predict_at_points(lons: np.ndarray, lats: np.ndarray, bundle: dict, config: MlConfig = DEFAULT_CONFIG) -> pd.DataFrame:
    """The real function a zone-prediction pipeline will call once zone
    centroids exist. Takes raw coordinates, does its own feature
    extraction -- same DEM/land-cover pipeline used for training."""
    feature_stack = build_feature_stack(config.paths.dem_utm_path, config)
    terrain = sample_at_points(feature_stack, lons, lats)

    landcover = sample_land_cover(lons, lats, config)
    one_hot = one_hot_encode(landcover["land_cover_class"])
    # Ensure every column the model was trained on exists, even if this
    # particular batch of points doesn't touch every land-cover class.
    for col in bundle["feature_cols"]:
        if col.startswith("landcover_") and col not in one_hot.columns:
            one_hot[col] = 0

    X = pd.concat([terrain, one_hot], axis=1)[bundle["feature_cols"]]
    scores = bundle["pipeline"].predict_proba(X)[:, 1]
    tiers = [score_to_tier(s, bundle["low_cut"], bundle["high_cut"]) for s in scores]

    return pd.DataFrame({
        "longitude": lons, "latitude": lats,
        "susceptibility_score": scores, "risk_tier": tiers,
        "model_version": bundle["model_version"],
        "in_bounds": terrain["in_bounds"].values,
    })


def demonstrate_on_training_points(config: MlConfig = DEFAULT_CONFIG) -> pd.DataFrame:
    bundle = load_model_bundle()
    df = pd.read_csv(config.paths.training_dataset_csv)
    preds = predict_at_points(df["longitude"].values, df["latitude"].values, bundle, config)
    preds["true_label"] = df["label"].values
    preds["district"] = df["district"].values

    out_path = ARTIFACT_DIR / "demo_point_predictions.csv"
    preds.to_csv(out_path, index=False)
    print(f"NOT real zone predictions -- demonstration on the {len(preds)} training-data points, "
          f"showing the prediction pipeline works end-to-end. Saved -> {out_path}")
    print("\nrisk_tier distribution:")
    print(preds["risk_tier"].value_counts())
    print("\nmean predicted score by true label (sanity check -- should be higher for actual positives):")
    print(preds.groupby("true_label")["susceptibility_score"].mean())
    return preds


if __name__ == "__main__":
    demonstrate_on_training_points()
