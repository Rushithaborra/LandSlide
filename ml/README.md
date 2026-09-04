# ML track — Landslide susceptibility model (Person B)

Status: real model trained and validated on real Sikkim data, served behind
an API ready for Person C to call. Day 2's hard checkpoint and Day 4's
integration task are both done.

## Setup

From the repo root:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt      # A's raster/GIS deps
pip install -r ml/requirements.txt   # ML/API deps on top of those
```

## Folder layout

```
ml/
  data/
    make_fake_data.py            # Day-1 practice dataset generator, superseded by real data, kept for reference
    fake_landslide_data.csv
    build_negative_features.py   # samples data/processed/*.tif rasters at A's negative points -> matching feature columns
    negative_features_for_B.csv  # output of the above, 766 rows
  notebooks/
    train_model.py          # validation pipeline: 75/25 split, AUC 0.774 (logreg) / 0.782 (rf)
    negative_sampling.py    # naive buffer-only method -- NOT used for the final dataset, see below
    diagnostics_*.png       # ROC curve + confusion matrix plots
  model/
    train_final_model.py         # retrains on ALL real rows (no held-out split) for deployment
    susceptibility_model.joblib  # the saved, deployed model (random forest)
    model_metadata.json          # validation numbers + feature list, also served at /model-info
  api/
    features.py   # (lat, lon) -> terrain feature dict, by sampling data/processed/*.tif
    app.py         # FastAPI service: GET /risk?lat=..&lon=.. -> risk score
    README.md      # integration instructions for Person C
  notes/
    methodology.md          # GSI factor list + published Sikkim rainfall thresholds
    handoff_format_for_A.md # exact CSV schema requested from Data/GIS lead
  requirements.txt

data/processed/sikkim_training_data.csv   # the real training set: A's handoff_for_B.csv
                                           # (765 landslide points) + negative_features_for_B.csv
                                           # (766 road-bias-matched safe points), 1531 rows total
```

The ML code reads directly from `data/processed/` and `data/raw/` (A's
existing folders) rather than keeping its own copies of the rasters —
avoids duplicating ~200MB of GeoTIFFs in git.

## Why there are two negative-sampling approaches in this repo

`notebooks/negative_sampling.py` (naive: random points + buffer exclusion)
was built on Day 1 before real data existed. Once A's real data arrived,
`data/PROVENANCE.md` revealed a real problem: 97% of actual landslide
reports are within 100m of a road (a reporting-location bias, not physics)
— a naive random negative set wouldn't correct for this, letting the model
cheat by learning "far from road = safe." A's own negative-sampling method
(`scripts/04_generate_negative_samples.py`, road-distance-matched) fixes
this properly, so the FINAL training set uses A's negative point locations
(`data/raw/sikkim_negative_samples.csv`), re-measured with our own feature
extraction (`ml/data/build_negative_features.py`) for consistency with the
positive points. `negative_sampling.py` is kept for reference/discussion,
not used in the final pipeline.

## What's real vs simulated right now

- **Real**: 765 real GSI-recorded landslide points, 766 road-bias-corrected
  negative points, both measured from the same real DEM/rainfall/land-cover
  rasters. Validated AUC (0.774–0.782) is a real held-out result, not
  invented. Feature importance checked and confirmed the model leans on
  real terrain factors (ruggedness, slope, elevation), not the suspected
  land-cover reporting-bias artifact.
- **Known, honest gap**: `lithology` (rock/soil type) is empty for every
  row — both GSI data portals are unreachable (see `data/PROVENANCE.md`).
  Dropped from training rather than fabricated. Say this plainly if asked.
- **Not yet real**: rainfall used in the API's `/risk` endpoint is the
  *static* mean-annual value baked into training, not live current rainfall
  — the dynamic trigger (Person C's job) is what layers in today's actual
  weather.

## Day-by-day

1. **Day 1**: env set up, pipeline built + verified on fake data,
   methodology + rainfall thresholds researched and cited, handoff spec sent to A.
2. **Day 2 (done)**: pulled A's real data from GitHub, discovered and
   corrected for the road-proximity reporting bias, merged into
   `data/processed/sikkim_training_data.csv`, trained on real data. AUC 0.774–0.782.
3. **Day 3 (done)**: validated (AUC, confusion matrix, feature importance
   sanity check). Calibration still open if there's time.
4. **Day 4 (done)**: model saved (`ml/model/susceptibility_model.joblib`),
   wrapped in a FastAPI service (`ml/api/app.py`) with a `/risk` endpoint ready
   for Person C to call. `ml/notes/methodology.md` already has the "how it
   works" two-layer explanation for the pitch.

## Quick start (to re-run everything now, from the repo root)

```bash
source venv/bin/activate

# Rebuild negative-point features from scratch (if data/processed/ is ever wiped)
python3 ml/data/build_negative_features.py

# Validate (prints AUC, confusion matrix, saves diagnostic plots)
python3 ml/notebooks/train_model.py

# Retrain the deployed model on all real data + save it
python3 ml/model/train_final_model.py

# Serve it
cd ml/api && uvicorn app:app --reload --port 8001
# then: curl "http://localhost:8001/risk?lat=27.3389&lon=88.6065"
```
