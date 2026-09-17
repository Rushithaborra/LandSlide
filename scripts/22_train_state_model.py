"""
Trains a landslide susceptibility model per state from
data/processed/training_dataset_<state>.csv. One generalized, config-free
script -- point it at any state slug, not a per-state copy.

Matches the Sikkim pipeline's own methodology (see the project's model
training report for Sikkim): Random Forest and Logistic Regression,
evaluated on SPATIAL block cross-validation (not a naive random split --
nearby points are spatially autocorrelated, so a random split leaks
information between train and test and inflates the reported score).
Uses scikit-learn throughout (RandomForestClassifier, LogisticRegression,
StandardScaler, roc_auc_score) rather than hand-rolled equivalents.

Per the team's own established rule: models are trained PER STATE, never
combined (Sikkim+Mizoram was tried together and rejected -- geologically
dissimilar states degraded each other's model quality). This script never
pools data across states.

Usage: python3 scripts/22_train_state_model.py <state_slug>

Outputs (data/models/<state>/):
  model.joblib              -- fitted pipeline (scaler + best model)
  metrics.csv                -- one row per (model type, CV fold): ROC-AUC,
                                 accuracy, precision, recall, F1
  metrics_summary.csv        -- one row per model type: mean +/- std ROC-AUC
                                 across folds, used to pick the best model
  predictions.csv             -- one row per training point: lon, lat,
                                 true label, out-of-fold predicted
                                 probability (never predicted on data the
                                 model was trained on)
  feature_importance.csv      -- one row per feature: importance score
                                 (permutation importance for the best model)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
MODELS = ROOT / "data" / "models"

FEATURE_COLS = [
    "elevation_m", "slope_deg", "aspect_deg", "distance_to_stream_m",
    "landcover_class", "soil_erodibility_k", "rusle_ls_factor",
    "rusle_c_factor", "rainfall_erosivity_r", "soil_loss_tha_yr",
]
LABEL_COL = "label"

# Spatial block CV, same scale as Sikkim's own methodology (2km cells).
BLOCK_SIZE_DEG = 0.018  # ~2km at these latitudes
N_FOLDS = 5
RANDOM_STATE = 42


def assign_spatial_blocks(df):
    """Grid-based spatial blocking: points in the same ~2km cell always
    land in the same fold, so a fold's test points are never adjacent to
    its train points -- the model can't just memorize local spatial
    autocorrelation and call it skill."""
    block_x = (df["lon"] // BLOCK_SIZE_DEG).astype(int)
    block_y = (df["lat"] // BLOCK_SIZE_DEG).astype(int)
    block_id = block_x.astype(str) + "_" + block_y.astype(str)
    unique_blocks = sorted(block_id.unique())
    rng = np.random.RandomState(RANDOM_STATE)
    rng.shuffle(unique_blocks)
    block_to_fold = {b: i % N_FOLDS for i, b in enumerate(unique_blocks)}
    return block_id.map(block_to_fold).values


def run(slug):
    csv_path = PROCESSED / f"training_dataset_{slug}.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"{csv_path} not found -- run the data pipeline (scripts 18-21) for {slug} first")

    df = pd.read_csv(csv_path).dropna(subset=FEATURE_COLS + [LABEL_COL, "lon", "lat"])
    print(f"=== Training model for {slug} ===")
    print(f"  {len(df)} points ({(df[LABEL_COL]==1).sum()} positive, {(df[LABEL_COL]==0).sum()} negative)")

    X = df[FEATURE_COLS].values
    y = df[LABEL_COL].values
    fold = assign_spatial_blocks(df)
    n_blocks = len(set(zip((df["lon"] // BLOCK_SIZE_DEG).astype(int), (df["lat"] // BLOCK_SIZE_DEG).astype(int))))
    print(f"  {n_blocks} spatial blocks (~{BLOCK_SIZE_DEG*111:.1f}km cells) across {N_FOLDS} folds")

    out_dir = MODELS / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    candidates = {
        "logistic_regression": Pipeline([
            ("scale", StandardScaler()),
            ("clf", LogisticRegression(max_iter=1000, random_state=RANDOM_STATE)),
        ]),
        "random_forest": Pipeline([
            ("clf", RandomForestClassifier(n_estimators=300, max_depth=12, random_state=RANDOM_STATE, n_jobs=-1)),
        ]),
    }

    metrics_rows = []
    oof_proba = {name: np.full(len(df), np.nan) for name in candidates}

    for fold_idx in range(N_FOLDS):
        train_mask = fold != fold_idx
        test_mask = fold == fold_idx
        if test_mask.sum() == 0 or len(set(y[train_mask])) < 2:
            print(f"  fold {fold_idx}: skipped (empty or single-class)")
            continue
        for name, pipeline in candidates.items():
            pipeline.fit(X[train_mask], y[train_mask])
            proba = pipeline.predict_proba(X[test_mask])[:, 1]
            oof_proba[name][test_mask] = proba
            preds = (proba >= 0.5).astype(int)
            y_test = y[test_mask]
            row = {
                "state": slug, "model": name, "fold": fold_idx, "n_test": int(test_mask.sum()),
                "roc_auc": roc_auc_score(y_test, proba) if len(set(y_test)) > 1 else float("nan"),
                "accuracy": accuracy_score(y_test, preds),
                "precision": precision_score(y_test, preds, zero_division=0),
                "recall": recall_score(y_test, preds, zero_division=0),
                "f1": f1_score(y_test, preds, zero_division=0),
            }
            metrics_rows.append(row)

    metrics_df = pd.DataFrame(metrics_rows)
    metrics_df.to_csv(out_dir / "metrics.csv", index=False)
    print(f"  wrote {out_dir / 'metrics.csv'}")

    summary_rows = []
    for name in candidates:
        sub = metrics_df[metrics_df["model"] == name]
        summary_rows.append({
            "state": slug, "model": name,
            "mean_roc_auc": sub["roc_auc"].mean(), "std_roc_auc": sub["roc_auc"].std(),
            "mean_f1": sub["f1"].mean(), "n_folds_evaluated": len(sub),
        })
    summary_df = pd.DataFrame(summary_rows).sort_values("mean_roc_auc", ascending=False)
    summary_df.to_csv(out_dir / "metrics_summary.csv", index=False)
    print(f"  wrote {out_dir / 'metrics_summary.csv'}")
    print(summary_df.to_string(index=False))

    best_name = summary_df.iloc[0]["model"]
    print(f"\n  Best model: {best_name} (mean spatial-CV ROC-AUC {summary_df.iloc[0]['mean_roc_auc']:.3f})")

    pred_df = df[["lon", "lat", LABEL_COL]].copy()
    pred_df["predicted_probability"] = oof_proba[best_name]
    pred_df.to_csv(out_dir / "predictions.csv", index=False)
    print(f"  wrote {out_dir / 'predictions.csv'} (out-of-fold predictions, never trained on)")

    # Refit the best model on ALL data for the saved artifact + feature importance.
    final_pipeline = candidates[best_name]
    final_pipeline.fit(X, y)
    import joblib
    joblib.dump(final_pipeline, out_dir / "model.joblib")
    print(f"  wrote {out_dir / 'model.joblib'}")

    perm = permutation_importance(final_pipeline, X, y, n_repeats=20, random_state=RANDOM_STATE, n_jobs=-1)
    importance_df = pd.DataFrame({
        "feature": FEATURE_COLS, "importance_mean": perm.importances_mean, "importance_std": perm.importances_std,
    }).sort_values("importance_mean", ascending=False)
    importance_df.to_csv(out_dir / "feature_importance.csv", index=False)
    print(f"  wrote {out_dir / 'feature_importance.csv'}")
    print(importance_df.to_string(index=False))


if __name__ == "__main__":
    run(sys.argv[1])
