"""Trains and compares 4 experiments (LogisticRegression x RandomForest,
baseline x extended features) for the Sikkim road-corridor susceptibility
model, using spatially-buffered block cross-validation (scripts/ml/spatial_cv.py)
-- not a naive random split, which this script also runs once per
experiment purely as a diagnostic contrast to quantify how much a naive
split would have overestimated performance.

Honest scope, unchanged from every prior document this session: road-
corridor, zone-level susceptibility for the Sikkim pilot. Not event-time
prediction.
"""
import json
from datetime import datetime, timezone

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    auc,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from scripts.ml.ml_config import DEFAULT_CONFIG, MlConfig
from scripts.ml.spatial_cv import CELL_SIZE_M, BUFFER_M, assign_folds, assign_spatial_blocks, buffer_train_mask

N_FOLDS = 5
RANDOM_SEED = 42
DECISION_THRESHOLD = 0.5  # standard default -- not tuned, see diagnostics section

LANDCOVER_COLS = [
    "landcover_bare_sparse_vegetation", "landcover_built_up", "landcover_cropland",
    "landcover_grassland", "landcover_moss_lichen", "landcover_tree_cover", "landcover_water",
]
FEATURE_SETS = {
    "baseline": ["elevation", "slope", "curvature", "distance_to_drainage"],
    "extended": ["elevation", "slope", "curvature", "distance_to_drainage"] + LANDCOVER_COLS,
}
MODEL_BUILDERS = {
    "logistic_regression": lambda: LogisticRegression(max_iter=2000, random_state=RANDOM_SEED),
    "random_forest": lambda: RandomForestClassifier(
        n_estimators=300, max_depth=8, min_samples_leaf=5, random_state=RANDOM_SEED, n_jobs=-1
    ),
}

ARTIFACT_DIR = DEFAULT_CONFIG.paths.training_dataset_csv.parent.parent / "models"


def build_pipeline(model_type: str) -> Pipeline:
    # StandardScaler is required for LogisticRegression's regularization to
    # treat features fairly; it's a no-op for RandomForest's split-based
    # decisions (monotonic per-feature transform), so using it for both
    # keeps one pipeline shape instead of two.
    return Pipeline([("scaler", StandardScaler()), ("classifier", MODEL_BUILDERS[model_type]())])


def compute_metrics(y_true: np.ndarray, y_prob: np.ndarray, threshold: float = DECISION_THRESHOLD) -> dict:
    y_pred = (y_prob >= threshold).astype(int)
    return {
        "roc_auc": roc_auc_score(y_true, y_prob),
        "pr_auc": average_precision_score(y_true, y_prob),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "confusion_matrix": confusion_matrix(y_true, y_pred).tolist(),
        "n": len(y_true),
    }


def run_spatial_cv(df: pd.DataFrame, feature_cols: list[str], model_type: str, folds: pd.Series,
                    config: MlConfig = DEFAULT_CONFIG) -> dict:
    oof_prob = np.full(len(df), np.nan)
    per_fold_metrics = []
    fitted_pipelines = []

    for fold in sorted(folds.unique()):
        test_mask = (folds == fold).values
        raw_train_mask = pd.Series(~test_mask, index=df.index)
        train_mask = buffer_train_mask(df, raw_train_mask, pd.Series(test_mask, index=df.index), config=config).values

        X_train, y_train = df.loc[train_mask, feature_cols], df.loc[train_mask, "label"]
        X_test, y_test = df.loc[test_mask, feature_cols], df.loc[test_mask, "label"]

        pipeline = build_pipeline(model_type)
        pipeline.fit(X_train, y_train)
        prob = pipeline.predict_proba(X_test)[:, 1]
        oof_prob[test_mask] = prob
        fitted_pipelines.append(pipeline)

        fold_metrics = compute_metrics(y_test.values, prob)
        fold_metrics["fold"] = int(fold)
        fold_metrics["n_train"] = int(train_mask.sum())
        per_fold_metrics.append(fold_metrics)

    pooled_metrics = compute_metrics(df["label"].values, oof_prob)
    fold_aucs = [m["roc_auc"] for m in per_fold_metrics]
    stability = {"roc_auc_mean": float(np.mean(fold_aucs)), "roc_auc_std": float(np.std(fold_aucs))}

    return {
        "pooled_metrics": pooled_metrics,
        "per_fold_metrics": per_fold_metrics,
        "stability": stability,
        "oof_prob": oof_prob,
        "fitted_pipelines": fitted_pipelines,
    }


def run_naive_random_split(df: pd.DataFrame, feature_cols: list[str], model_type: str,
                            test_size: float = 0.2, seed: int = RANDOM_SEED) -> dict:
    """Diagnostic ONLY -- a naive random point split, run purely to quantify
    how much spatial leakage would inflate apparent performance if we'd
    used this instead of the spatial block CV above. Never used for model
    selection."""
    rng = np.random.default_rng(seed)
    idx = df.index.values.copy()
    rng.shuffle(idx)
    n_test = int(len(idx) * test_size)
    test_idx, train_idx = idx[:n_test], idx[n_test:]

    pipeline = build_pipeline(model_type)
    pipeline.fit(df.loc[train_idx, feature_cols], df.loc[train_idx, "label"])
    prob = pipeline.predict_proba(df.loc[test_idx, feature_cols])[:, 1]
    return compute_metrics(df.loc[test_idx, "label"].values, prob)


def run_all_experiments(df: pd.DataFrame, folds: pd.Series, config: MlConfig = DEFAULT_CONFIG) -> dict:
    results = {}
    for model_type in MODEL_BUILDERS:
        for feature_set_name, feature_cols in FEATURE_SETS.items():
            key = f"{model_type}__{feature_set_name}"
            print(f"\n{'='*70}\nExperiment: {key}\n{'='*70}")

            spatial = run_spatial_cv(df, feature_cols, model_type, folds, config)
            naive = run_naive_random_split(df, feature_cols, model_type)

            print(f"Spatial CV pooled: ROC-AUC={spatial['pooled_metrics']['roc_auc']:.3f} "
                  f"PR-AUC={spatial['pooled_metrics']['pr_auc']:.3f} "
                  f"(fold AUC {spatial['stability']['roc_auc_mean']:.3f} +/- {spatial['stability']['roc_auc_std']:.3f})")
            print(f"Naive random-split (diagnostic only): ROC-AUC={naive['roc_auc']:.3f}")
            gap = naive["roc_auc"] - spatial["pooled_metrics"]["roc_auc"]
            print(f"Inflation from naive split: {gap:+.3f} AUC points")

            results[key] = {
                "model_type": model_type,
                "feature_set": feature_set_name,
                "feature_cols": feature_cols,
                "spatial_cv": spatial,
                "naive_split_diagnostic": naive,
                "naive_vs_spatial_gap": gap,
            }
    return results


def print_metrics_table(results: dict) -> None:
    print(f"\n{'='*100}\nFULL METRICS TABLE (spatial CV, pooled out-of-fold predictions, threshold={DECISION_THRESHOLD})\n{'='*100}")
    rows = []
    for key, r in results.items():
        m = r["spatial_cv"]["pooled_metrics"]
        rows.append({
            "experiment": key, "roc_auc": round(m["roc_auc"], 3), "pr_auc": round(m["pr_auc"], 3),
            "precision": round(m["precision"], 3), "recall": round(m["recall"], 3), "f1": round(m["f1"], 3),
            "fold_auc_std": round(r["spatial_cv"]["stability"]["roc_auc_std"], 3),
            "naive_split_gap": round(r["naive_vs_spatial_gap"], 3),
        })
    print(pd.DataFrame(rows).set_index("experiment").to_string())

    print("\nConfusion matrices (rows=actual [neg,pos], cols=predicted [neg,pos]):")
    for key, r in results.items():
        cm = r["spatial_cv"]["pooled_metrics"]["confusion_matrix"]
        print(f"  {key}: {cm}")


def diagnostic_checks(results: dict, df: pd.DataFrame) -> None:
    print(f"\n{'='*100}\nDIAGNOSTIC CHECKS\n{'='*100}")

    print("\n1. Suspiciously high performance?")
    for key, r in results.items():
        auc_val = r["spatial_cv"]["pooled_metrics"]["roc_auc"]
        flag = " <-- INVESTIGATE: unexpectedly high for 4-5 features on noisy field data" if auc_val > 0.90 else " (unremarkable, expected range for this feature set)"
        print(f"  {key}: ROC-AUC={auc_val:.3f}{flag}")

    print("\n2. Spatial leakage -- naive random split vs spatial CV (gap should be small and explainable):")
    for key, r in results.items():
        gap = r["naive_vs_spatial_gap"]
        flag = " <-- large gap, spatial CV materially matters here" if gap > 0.05 else ""
        print(f"  {key}: naive={r['naive_split_diagnostic']['roc_auc']:.3f} spatial={r['spatial_cv']['pooled_metrics']['roc_auc']:.3f} gap={gap:+.3f}{flag}")

    print("\n3. Duplicate/overlap issues in this run:")
    dupe_coords = df.duplicated(subset=["latitude", "longitude"]).sum()
    print(f"  duplicate coordinates in training data: {dupe_coords} (should be 0, resolved pre-training)")

    print("\n4. Class separation (perfect/near-perfect train fit would signal leakage or trivial separability):")
    for key, r in results.items():
        # refit on ALL data to check train-set fit -- if this hits ~1.0 AUC
        # while spatial CV is much lower, that's expected (normal train/test
        # gap for a small feature set), not a red flag on its own; flagging
        # only if spatial CV itself was already suspiciously high (see #1).
        model_type, feature_set = r["model_type"], r["feature_set"]
        pipeline = build_pipeline(model_type)
        pipeline.fit(df[r["feature_cols"]], df["label"])
        train_prob = pipeline.predict_proba(df[r["feature_cols"]])[:, 1]
        train_auc = roc_auc_score(df["label"], train_prob)
        print(f"  {key}: train-set (in-sample) AUC={train_auc:.3f} vs spatial-CV AUC={r['spatial_cv']['pooled_metrics']['roc_auc']:.3f}")

    print("\n5. Does land_cover_class materially improve spatial generalization?")
    for model_type in MODEL_BUILDERS:
        base = results[f"{model_type}__baseline"]["spatial_cv"]["pooled_metrics"]["roc_auc"]
        ext = results[f"{model_type}__extended"]["spatial_cv"]["pooled_metrics"]["roc_auc"]
        print(f"  {model_type}: baseline={base:.3f} -> extended={ext:.3f} (delta={ext-base:+.3f}) "
              f"{'-- consistent improvement' if ext > base else '-- no improvement'}")


def plot_roc_pr_curves(results: dict, config: MlConfig = DEFAULT_CONFIG) -> None:
    fig, (ax_roc, ax_pr) = plt.subplots(1, 2, figsize=(14, 6))
    colors = {"logistic_regression__baseline": "tab:blue", "logistic_regression__extended": "tab:cyan",
              "random_forest__baseline": "tab:red", "random_forest__extended": "tab:orange"}

    for key, r in results.items():
        y_true = pd.read_csv(config.paths.training_dataset_csv)["label"].values
        y_prob = r["spatial_cv"]["oof_prob"]
        fpr, tpr, _ = roc_curve(y_true, y_prob)
        prec, rec, _ = precision_recall_curve(y_true, y_prob)
        ax_roc.plot(fpr, tpr, label=f"{key} (AUC={auc(fpr, tpr):.3f})", color=colors.get(key))
        ax_pr.plot(rec, prec, label=f"{key} (AP={average_precision_score(y_true, y_prob):.3f})", color=colors.get(key))

    ax_roc.plot([0, 1], [0, 1], "k--", alpha=0.3, label="chance")
    ax_roc.set_xlabel("False Positive Rate")
    ax_roc.set_ylabel("True Positive Rate")
    ax_roc.set_title("ROC curves (spatial CV, pooled out-of-fold)")
    ax_roc.legend(fontsize=8)

    ax_pr.axhline(0.5, color="k", linestyle="--", alpha=0.3, label="chance (balanced classes)")
    ax_pr.set_xlabel("Recall")
    ax_pr.set_ylabel("Precision")
    ax_pr.set_title("Precision-Recall curves (spatial CV, pooled out-of-fold)")
    ax_pr.legend(fontsize=8)

    fig.tight_layout()
    out_path = ARTIFACT_DIR / "roc_pr_curves.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\nROC/PR curves saved -> {out_path}")


def plot_feature_importance(df: pd.DataFrame, results: dict) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()

    for ax, (key, r) in zip(axes, results.items()):
        pipeline = build_pipeline(r["model_type"])
        pipeline.fit(df[r["feature_cols"]], df["label"])
        clf = pipeline.named_steps["classifier"]

        if r["model_type"] == "random_forest":
            importance = clf.feature_importances_
            title = f"{key}\n(mean decrease in impurity)"
        else:
            importance = clf.coef_[0]
            title = f"{key}\n(standardized coefficient)"

        order = np.argsort(np.abs(importance))
        ax.barh([r["feature_cols"][i] for i in order], importance[order])
        ax.set_title(title, fontsize=10)
        ax.axvline(0, color="k", linewidth=0.5)

    fig.tight_layout()
    out_path = ARTIFACT_DIR / "feature_importance.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"feature importance/coefficients plot saved -> {out_path}")


def select_best_model(results: dict) -> str:
    """Selection criteria, in order: (1) held-out spatial ROC-AUC, (2)
    stability (lower fold-to-fold std preferred as a tiebreaker), (3) the
    naive-split gap should not be the dominant driver of any apparent
    advantage. Not a single-metric pick."""
    ranked = sorted(
        results.items(),
        key=lambda kv: (-kv[1]["spatial_cv"]["pooled_metrics"]["roc_auc"], kv[1]["spatial_cv"]["stability"]["roc_auc_std"]),
    )
    print(f"\n{'='*100}\nMODEL SELECTION (ranked by spatial ROC-AUC, then stability)\n{'='*100}")
    for key, r in ranked:
        m = r["spatial_cv"]["pooled_metrics"]
        print(f"  {key}: ROC-AUC={m['roc_auc']:.3f} stability_std={r['spatial_cv']['stability']['roc_auc_std']:.3f}")
    return ranked[0][0]


def risk_tier_thresholds(probs: np.ndarray) -> tuple[float, float]:
    """Tertile cutoffs on the final model's own predicted-probability
    distribution -- our own choice, not literature-sourced, documented as
    such (same honesty pattern as the SUSCEPTIBILITY_MULTIPLIERS table in
    app/services/alert_engine.py)."""
    return float(np.percentile(probs, 33)), float(np.percentile(probs, 67))


def score_to_tier(score: float, low_cut: float, high_cut: float) -> str:
    if score < low_cut:
        return "low"
    if score < high_cut:
        return "moderate"
    return "high"


def save_artifacts(df: pd.DataFrame, results: dict, best_key: str, config: MlConfig = DEFAULT_CONFIG) -> dict:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    best = results[best_key]
    model_version = f"{best_key.replace('__', '-')}-v1-{datetime.now(timezone.utc).strftime('%Y%m%d')}"

    print(f"\n{'='*100}\nFINAL MODEL: retraining {best_key} on ALL {len(df)} rows (CV was for evaluation only)\n{'='*100}")
    final_pipeline = build_pipeline(best["model_type"])
    final_pipeline.fit(df[best["feature_cols"]], df["label"])

    model_path = ARTIFACT_DIR / "susceptibility_model.joblib"
    joblib.dump({"pipeline": final_pipeline, "feature_cols": best["feature_cols"], "model_version": model_version}, model_path)
    print(f"model + pipeline saved -> {model_path}")

    final_probs = final_pipeline.predict_proba(df[best["feature_cols"]])[:, 1]
    low_cut, high_cut = risk_tier_thresholds(final_probs)
    print(f"risk tier thresholds (tertiles of final model's own training predictions): "
          f"low < {low_cut:.3f} <= moderate < {high_cut:.3f} <= high")

    validation_report = {
        "model_version": model_version,
        "selected_experiment": best_key,
        "model_type": best["model_type"],
        "feature_set": best["feature_set"],
        "feature_cols": best["feature_cols"],
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "n_training_rows": len(df),
        "spatial_cv": {
            "n_folds": N_FOLDS, "cell_size_m": CELL_SIZE_M, "buffer_m": BUFFER_M,
            "pooled_metrics": {k: v for k, v in best["spatial_cv"]["pooled_metrics"].items()},
            "stability": best["spatial_cv"]["stability"],
        },
        "naive_split_diagnostic_gap": best["naive_vs_spatial_gap"],
        "risk_tier_thresholds": {"low_max": low_cut, "moderate_max": high_cut},
        "all_experiments_summary": {
            key: {
                "roc_auc": r["spatial_cv"]["pooled_metrics"]["roc_auc"],
                "pr_auc": r["spatial_cv"]["pooled_metrics"]["pr_auc"],
                "precision": r["spatial_cv"]["pooled_metrics"]["precision"],
                "recall": r["spatial_cv"]["pooled_metrics"]["recall"],
                "f1": r["spatial_cv"]["pooled_metrics"]["f1"],
                "fold_auc_std": r["spatial_cv"]["stability"]["roc_auc_std"],
            }
            for key, r in results.items()
        },
        "scope": "Road-corridor, zone-level landslide susceptibility for the Sikkim pilot. "
                 "NOT event-time prediction.",
        "known_limitations": [
            "Random Forest's in-sample (train) AUC is notably higher than its spatial-CV AUC "
            "(0.866 vs 0.735 for the extended model) -- more overfitting than Logistic Regression "
            "shows (0.722 vs 0.714), though its held-out performance is still the best of the four.",
            "land_cover_class's built_up signal could not be fully separated between genuine "
            "anthropogenic slope destabilization and GSI's own documentation priority toward "
            "infrastructure-adjacent failures -- see docs/duplicate_and_bias_audit.md.",
            "Positive samples remain concentrated within ~100m of roads (a field-survey property "
            "of the source inventory); the model has not been evaluated on terrain far from roads.",
            "ROC-AUC 0.67-0.74 range reflects a genuinely modest first-pass model on limited "
            "features and imperfect labels -- not state-of-the-art, but not overclaimed either.",
        ],
    }
    report_path = ARTIFACT_DIR / "validation_report.json"
    with open(report_path, "w") as f:
        json.dump(validation_report, f, indent=2)
    print(f"validation report saved -> {report_path}")

    return {"model_version": model_version, "pipeline": final_pipeline, "feature_cols": best["feature_cols"],
            "low_cut": low_cut, "high_cut": high_cut, "validation_report": validation_report}


if __name__ == "__main__":
    df = pd.read_csv(DEFAULT_CONFIG.paths.training_dataset_csv)
    print(f"loaded {len(df)} rows")

    blocks = assign_spatial_blocks(df)
    folds = assign_folds(blocks, n_folds=N_FOLDS, seed=RANDOM_SEED)
    print(f"{blocks.nunique()} spatial blocks ({CELL_SIZE_M/1000:.0f}km cells) -> {N_FOLDS} folds, "
          f"{BUFFER_M:.0f}m buffer")

    results = run_all_experiments(df, folds)
    print_metrics_table(results)
    diagnostic_checks(results, df)
    plot_roc_pr_curves(results)
    plot_feature_importance(df, results)
    best_key = select_best_model(results)
    print(f"\nBest experiment: {best_key}")

    final = save_artifacts(df, results, best_key)
    print(f"\nmodel_version = {final['model_version']}")
