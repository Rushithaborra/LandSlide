# Susceptibility API — for Person C (backend)

This is the ML model wrapped as an HTTP service. Your backend calls this;
it does not need to know anything about scikit-learn, rasters, or the model
internals.

## Run it

```bash
cd ml/api
source ../venv/bin/activate
uvicorn app:app --reload --port 8001
```

## Endpoints

### `GET /risk?lat={lat}&lon={lon}`

The main one. Give it any coordinate inside Sikkim.

```bash
curl "http://localhost:8001/risk?lat=27.3389&lon=88.6065"
```

```json
{
  "lat": 27.3389,
  "lon": 88.6065,
  "risk_score": 0.42,
  "risk_class": "medium",
  "features_used": { "elevation": 1508.4, "slope_deg": 19.7, "...": "..." },
  "note": "Static terrain susceptibility only -- does not include live rainfall...",
  "known_gap": "lithology not included -- GSI data source unavailable, not fabricated"
}
```

- `risk_score`: 0-1, this point's terrain susceptibility.
- `risk_class`: `low` (<0.35), `medium` (0.35-0.65), `high` (>0.65) — thresholds
  are a starting point, tune them once we see the full score distribution.
- A coordinate outside Sikkim's data coverage returns HTTP 422, not a
  silently wrong score.

**Important — this is the static half only.** Per the team's two-layer
design (notes/methodology.md), your rainfall-threshold trigger is the
dynamic half. The actual alert decision is:

```
alert = (risk_score from this API is high) AND (today's rainfall crosses
         the Sikkim/Gangtok threshold curve)
```

Don't fire alerts off this endpoint alone.

### `GET /model-info`

Validation numbers, feature list, and known gaps (lithology) — useful for
your own sanity checks and directly answers the pitch's "how accurate is
your model" / "is this AI or just rules" questions. Feed this straight into
F's Q&A prep if useful.

### `GET /health`

Just confirms the service and model are loaded.

## What this depends on

The raster files in `ml/data/rasters/` (elevation, slope, aspect, etc.) and
the saved model in `ml/model/susceptibility_model.joblib` — both already in
this repo. If you deploy this as a separate service (e.g. on a different
machine from the main backend), those files need to travel with it.
