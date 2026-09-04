"""
Trains the model that actually gets deployed behind the API -- separate from
notebooks/train_model.py, which exists to VALIDATE (held-out test split,
AUC, confusion matrix). This script re-trains on ALL real rows (no held-out
split) so the deployed model learns from every real data point available.
Standard practice: prove the method works on a held-out split first
(notebooks/train_model.py already did that -- AUC 0.774 logreg / 0.782 rf),
then retrain the final deployed version on the full dataset once trusted.

Model choice: RandomForestClassifier, not logistic regression, even though
the held-out AUCs were close (0.782 vs 0.774). The reason is recall on the
landslide class specifically -- rf caught 82% of real landslide points on
the held-out set vs logreg's 70%. For an early-warning system, missing a
genuinely dangerous zone (false negative) is worse than flagging a safe
zone as risky (false positive), so the higher-recall model is the better
operational choice. It's still explainable via feature importances (checked:
terrain factors dominate, not the suspected land-cover reporting-bias
artifact -- see data/PROVENANCE.md), just not as simple to narrate
line-by-line as logistic regression -- if a judge asks for the simplest
possible explanation, logreg is the fallback answer.

Run from the repo root: python ml/model/train_final_model.py
Outputs (both loaded by ml/api/app.py):
  ml/model/susceptibility_model.joblib  -- the trained sklearn Pipeline
  ml/model/model_metadata.json          -- validation numbers + feature list
"""

import json
import sys
from pathlib import Path

import joblib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "notebooks"))
from train_model import (  # noqa: E402
    CATEGORICAL_FEATURES,
    DATA_PATH,
    LABEL_COL,
    NUMERIC_FEATURES,
    build_pipeline,
    load_data,
)

OUT_DIR = Path(__file__).resolve().parent


def main():
    df = load_data(DATA_PATH)
    X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y = df[LABEL_COL]

    pipeline = build_pipeline("rf")
    pipeline.fit(X, y)

    model_path = OUT_DIR / "susceptibility_model.joblib"
    joblib.dump(pipeline, model_path)

    metadata = {
        "model_type": "RandomForestClassifier",
        "trained_on_rows": len(df),
        "positive_rows": int(y.sum()),
        "negative_rows": int((y == 0).sum()),
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "excluded_features": {
            "lithology": "GSI Bhukosh + NGDR both unreachable -- column is 100% empty, dropped rather than fabricated"
        },
        "held_out_validation": {
            "note": "from notebooks/train_model.py's 75/25 split, NOT this file's full-data fit",
            "logreg_auc": 0.774,
            "random_forest_auc": 0.782,
            "random_forest_recall_landslide_class": 0.82,
            "logreg_recall_landslide_class": 0.70,
            "chosen_model": "random_forest",
            "why": "higher recall on the landslide class matters more than a small AUC edge for an early-warning use case -- missing a real danger zone is costlier than a false alarm",
        },
        "negative_sampling_method": "road-distance-matched (Person A), not naive buffer-only -- see data/build_negative_features.py",
    }
    metadata_path = OUT_DIR / "model_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2))

    print(f"Saved model to {model_path}")
    print(f"Saved metadata to {metadata_path}")
    print(f"Trained on {len(df)} rows ({int(y.sum())} landslide, {int((y==0).sum())} non-landslide)")


if __name__ == "__main__":
    main()
