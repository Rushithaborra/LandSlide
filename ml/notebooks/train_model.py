"""
Susceptibility model training + validation pipeline.

Runs on REAL Sikkim data: data/processed/sikkim_training_data.csv, built
from A's handoff_for_B.csv (765 real GSI landslide points) merged with A's
road-bias-matched negative samples (766 points, features extracted by
../data/build_negative_features.py using the same raster-sampling method A
used for the positives -- see that file's docstring for why this matters
more than a naive buffer-only negative set).

lithology is dropped from CATEGORICAL_FEATURES: both GSI portals that would
supply it are unreachable (see data/PROVENANCE.md), so the column is 100%
empty for every row -- not fabricated, just genuinely missing right now.
Add it back once real values arrive.

Run from the repo root: python ml/notebooks/train_model.py
"""

from pathlib import Path

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    RocCurveDisplay,
    classification_report,
    confusion_matrix,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = REPO_ROOT / "data" / "processed" / "sikkim_training_data.csv"

NUMERIC_FEATURES = ["elevation", "slope_deg", "aspect_deg", "drainage_density",
                     "mean_annual_rainfall_mm", "curvature", "distance_to_drainage", "terrain_ruggedness"]
CATEGORICAL_FEATURES = ["landuse"]  # lithology excluded -- see module docstring
LABEL_COL = "label"


def load_data(path=DATA_PATH):
    df = pd.read_csv(path)
    missing = [c for c in NUMERIC_FEATURES + CATEGORICAL_FEATURES + [LABEL_COL] if c not in df.columns]
    if missing:
        raise ValueError(f"Data is missing expected columns: {missing}")
    return df


def build_pipeline(model_name="logreg"):
    """model_name: 'logreg' (default, simplest to explain) or 'rf' (random forest)."""
    preprocessor = ColumnTransformer([
        ("num", StandardScaler(), NUMERIC_FEATURES),
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
    ])

    if model_name == "logreg":
        model = LogisticRegression(max_iter=1000)
    elif model_name == "rf":
        model = RandomForestClassifier(n_estimators=300, max_depth=8, random_state=42)
    else:
        raise ValueError("model_name must be 'logreg' or 'rf'")

    return Pipeline([
        ("preprocess", preprocessor),
        ("model", model),
    ])


def train_and_validate(df, model_name="logreg"):
    X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y = df[LABEL_COL]

    # Held-out test set: the model never sees these points during training.
    # stratify=y keeps the landslide/non-landslide ratio the same in both splits.
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    pipeline = build_pipeline(model_name)
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test)[:, 1]  # risk score, 0-1

    auc = roc_auc_score(y_test, y_proba)
    cm = confusion_matrix(y_test, y_pred)

    print(f"\n=== Model: {model_name} ===")
    print(f"AUC-ROC on held-out points: {auc:.3f}")
    print("\nConfusion matrix (rows=actual, cols=predicted, order=[0,1]):")
    print(cm)
    print("\nClassification report:")
    print(classification_report(y_test, y_pred, target_names=["no landslide", "landslide"]))

    return pipeline, X_test, y_test, y_proba, auc, cm


def plot_diagnostics(pipeline, X_test, y_test, model_name):
    """Saves ROC curve and confusion matrix plots for the pitch deck / sanity check."""
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    RocCurveDisplay.from_estimator(pipeline, X_test, y_test, ax=axes[0])
    axes[0].set_title("ROC Curve")

    ConfusionMatrixDisplay.from_estimator(
        pipeline, X_test, y_test, display_labels=["no landslide", "landslide"], ax=axes[1]
    )
    axes[1].set_title("Confusion Matrix")

    fig.suptitle(f"Susceptibility model diagnostics ({model_name})")
    fig.tight_layout()
    out_path = Path(__file__).resolve().parent / f"diagnostics_{model_name}.png"
    fig.savefig(out_path, dpi=150)
    print(f"\nSaved diagnostics plot to {out_path}")


if __name__ == "__main__":
    df = load_data(DATA_PATH)
    print(f"Loaded {len(df)} rows ({df[LABEL_COL].sum()} landslide, {(df[LABEL_COL] == 0).sum()} non-landslide)")

    for name in ["logreg", "rf"]:
        pipeline, X_test, y_test, y_proba, auc, cm = train_and_validate(df, model_name=name)
        plot_diagnostics(pipeline, X_test, y_test, model_name=name)
