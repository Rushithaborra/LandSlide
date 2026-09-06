# Connecting Person B's real susceptibility model

Discovered late (2026-09-06): Person B (the actual ML lead) built a complete,
separate, real ML pipeline on the `ml-integration` branch of this same
GitHub repo — real DEM, real GSI landslide inventory (765 points), a RUSLE
erosion model, real terrain rasters, trained into a Random Forest (held-out
AUC 0.774-0.782). Their own `ml/api/README.md` says explicitly: **"this is
what Person C's backend calls."** That connection had never actually been
made — this directory's own earlier ML groundwork (`scripts/ml/`) was a
placeholder built before this branch existed, not B's real deliverable.

## What this does

Person B's design intent was a live HTTP API (`GET /risk?lat=..&lon=..`)
that the backend calls per-request. Running that as a persistent service in
production would mean deploying ~200MB of raster files to Render's free
tier — not practical for this round. Instead, `push_real_predictions.py`:

1. Fetches every zone currently in production (each already has a
   `centroid_lat`/`centroid_lng`, computed server-side from its polygon)
2. Runs each centroid through B's actual model, using B's own
   `features.py` feature-extraction logic (samples B's real raster layers
   at that exact point)
3. Pushes the result through the **existing, unmodified**
   `PUT /zones/{id}/susceptibility` endpoint — the same contract B's
   README documents, and the same one this project's own groundwork model
   already used

`model_version` is set to `personB-random_forest-v1-20260902` for every
zone this touches, so it's honestly distinguishable from
`random_forest-extended-v1-20260902` (this project's own earlier
groundwork model) if anyone asks which model produced a given score.

## Result (run 2026-09-06)

- **3411 of 3921 zones** updated with B's real model output
- **510 zones** fall outside B's raster coverage area (mostly one long
  road, NH717A, extending past it) — left on the groundwork model's score
  rather than guessed. B's own `features.py` raises `OutOfCoverageError`
  for these; we surface that, not paper over it.
- 2 transient network failures on first pass, succeeded on retry

## To reproduce

Person B's model file and rasters aren't committed here (same reasoning as
this project's own `data/raw/`, `data/processed/` — large geodata, not
meant for git). Pull them from the `ml-integration` branch instead:

```bash
BASE="https://raw.githubusercontent.com/Rushithaborra/LandSlide/ml-integration"
mkdir -p model rasters
curl -o model/susceptibility_model.joblib "$BASE/ml/model/susceptibility_model.joblib"
curl -o model/model_metadata.json "$BASE/ml/model/model_metadata.json"
for f in dem_sikkim_utm45n slope_deg aspect_deg drainage_density landcover_sikkim_utm45n \
         mean_annual_rainfall_mm distance_to_stream_m curvature terrain_ruggedness; do
  curl -o "rasters/$f.tif" "$BASE/data/processed/$f.tif"
done

python push_real_predictions.py        # full run
python push_real_predictions.py 10     # test with just 10 zones first
```

Requires `rasterio`, `pyproj`, `joblib`, `pandas`, `scikit-learn`, `httpx` —
all already in this project's main `requirements.txt`.
