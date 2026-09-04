"""
Susceptibility model API -- this is what Person C's backend calls.

One real endpoint: GET /risk?lat=..&lon=..
Give it any coordinate inside Sikkim, it returns a static susceptibility
score for that terrain. This is the "static" half of the two-layer risk
system (see notes/methodology.md) -- it does NOT know about today's
rainfall. C's backend is responsible for combining this score with the
live rainfall-threshold trigger to decide whether to actually fire an alert:

    alert = (this API's risk_score is high) AND (today's rainfall crosses
             the Sikkim/Gangtok threshold from notes/methodology.md)

Run: uvicorn app:app --reload --port 8001
Then: curl "http://localhost:8001/risk?lat=27.3389&lon=88.6065"
"""

import json
from pathlib import Path

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from features import OutOfCoverageError, get_features_at_point

MODEL_DIR = Path(__file__).resolve().parents[1] / "model"

app = FastAPI(title="Sikkim Landslide Susceptibility API")

# Dashboard (Person D) likely runs on a different origin (e.g. localhost:3000) --
# without this, browser fetches from the dashboard would be blocked by CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_pipeline = joblib.load(MODEL_DIR / "susceptibility_model.joblib")
_metadata = json.loads((MODEL_DIR / "model_metadata.json").read_text())

FEATURE_COLUMNS = _metadata["numeric_features"] + _metadata["categorical_features"]


def _risk_class(score: float) -> str:
    if score < 0.35:
        return "low"
    elif score < 0.65:
        return "medium"
    return "high"


@app.get("/health")
def health():
    return {"status": "ok", "model_type": _metadata["model_type"]}


@app.get("/model-info")
def model_info():
    """For the pitch's 'how it works' slide / Q&A -- what the model is, how it
    was validated, and what's explicitly missing (lithology)."""
    return _metadata


@app.get("/risk")
def risk(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
):
    try:
        features = get_features_at_point(lat, lon)
    except OutOfCoverageError as e:
        raise HTTPException(status_code=422, detail=str(e))

    X = pd.DataFrame([{col: features[col] for col in FEATURE_COLUMNS}])
    score = float(_pipeline.predict_proba(X)[0, 1])

    return {
        "lat": lat,
        "lon": lon,
        "risk_score": round(score, 4),
        "risk_class": _risk_class(score),
        "features_used": features,
        "note": "Static terrain susceptibility only -- does not include live rainfall. "
                "Combine with the rainfall-threshold trigger for a full alert decision.",
        "known_gap": "lithology not included -- GSI data source unavailable, not fabricated",
    }
