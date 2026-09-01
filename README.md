# Landslide EWS — Backend

FastAPI + PostgreSQL/PostGIS backend for the SIH 2026 (PS 26001) prototype.
Backend scope only: API, DB schema, rainfall ingestion, rule-based alert
trigger, citizen report intake. See `CLAUDE.md` for the full project brief,
and `docs/` for the team roadmap, the internal 4-day plan, and the pitch deck.

## Two-layer risk model
- **Static (ML-owned):** `zones.susceptibility_score` / `risk_tier` /
  `model_version` — written via `PUT /zones/{id}/susceptibility` by the ML
  lead's pipeline. Backend reads/serves it, never computes it. Contract:
  `susceptibility_score` (0-1), `risk_tier` (low/moderate/high),
  `model_version` (free text — e.g. `rf-v1` or a training-run commit hash).
- **Dynamic (rules, this backend's job):** `app/services/alert_engine.py`
  checks rainfall against a configurable intensity-duration (I-D) curve, then
  scales that curve by the zone's `risk_tier` (high-susceptibility zones
  alert at a lower rainfall bar). Rule-based on purpose, not disguised as ML.

## Implemented / Simulated / Pending

**Implemented and verified this session:**
- FastAPI skeleton boots; all routes registered (`/zones`, `/rainfall`,
  `/alerts`, `/reports`, `/health`)
- Open-Meteo daily-rainfall integration — live-verified (`past_days` +
  `forecast_days`, matching the daily granularity the I-D threshold model needs)
- Rainfall intensity-duration threshold is **config-driven**, not hardcoded —
  see `app/config.py` (`RainfallThresholdConfig`) and `.env.example`. Current
  value sourced from Harilal, Madhu, Ramesh & Pullarkatt (2019), *Landslides*
  16(12), DOI 10.1007/s10346-019-01244-1 — a real, Sikkim-specific paper
  (Sikkim is the roadmap's recommended pilot state). **Not verified against
  the primary text** (paywalled) — `verified_against_primary_text: false` in
  config until someone on the team confirms the coefficients directly.
- Susceptibility × rainfall combination: `SUSCEPTIBILITY_MULTIPLIERS` in
  `alert_engine.py` scales the threshold by risk tier. This multiplier table
  is **our own explainable rule**, not literature-sourced — say so if asked.
- 12 passing unit tests (`tests/test_alert_engine.py`) covering low/moderate/
  high susceptibility scaling, threshold breach and no-breach (including a
  sustained-rain-over-longer-duration case a same-day cutoff would miss), and
  invalid rainfall input (negative, NaN, None, infinite) raising `ValueError`
  instead of silently misbehaving
- ML → backend contract finalized: `PUT /zones/{id}/susceptibility` takes
  `susceptibility_score`, `risk_tier`, `model_version`

**Simulated / not implemented — flag these if asked:**
- Rainfall source is **Open-Meteo only**. The pitch deck's tech-stack slide
  names IMD as primary with Open-Meteo as fallback — in practice IMD access
  wasn't reachable in this timeframe, so Open-Meteo is what's actually live.
  Treat IMD as a documented future/primary institutional integration, not
  something currently wired up.
- SMS delivery: **not implemented.** Alerts are written to the `alerts` table
  and printed to the server log only (`delivery_method="log_only"`). No
  Twilio/MSG91 work planned unless there's spare time later.
- Citizen report photo upload: this API accepts a `photo_url` string only —
  it does not host file uploads. Reporting lead's form needs to upload the
  photo somewhere and pass the resulting URL.
- No auth on any endpoint — out of scope for this round.

**Resolved 2026-09-01** — a native Postgres 18 + PostGIS 3.6 now runs locally
(`bin/pgsql`, no Docker/admin rights needed — see `CLAUDE.md` "Environment
notes"). `migrations/001_schema.sql` applied for real; `/reports` verified
end-to-end against the live DB (real insert, real photo upload, real public
URL via `scripts/run_public_dev_server.ps1`). `/zones`, `/rainfall`,
`/alerts` should also work now but haven't each been individually
re-exercised against this DB yet.

**Still pending:**
- Running `scripts/seed_zone.py` for real (needs a real pilot zone boundary
  from Data/GIS lead — schema/DB side is ready)
- A true "alert fires live" rehearsal against real ingested data

## ML data pipeline (`scripts/ml/`)

**Scope, stated plainly:** this is a **road-corridor** susceptibility model,
not full-state. The GSI Sikkim inventory is 96.1%-within-100m-of-a-mapped-road
(measured against real OpenStreetMap geometry) — a field-survey artifact, not
evidence that susceptibility itself is road-proximate. We lean into this
intentionally: it matches the project's own road-connectivity framing
(flagging at-risk road segments), not a limitation being hidden. Don't claim
full-state coverage from this dataset.

**Two-layer architecture preserved:** rainfall stays out of the static
susceptibility dataset entirely. `scripts/ml/rainfall_threshold_case_study.py`
is a *separate* validation exercise for the existing rainfall rule engine
(`app/services/alert_engine.py`) against 68 precisely-dated historical
events — its output lives in `data/case_study/`, never joined into
`data/processed/training_dataset.csv`.

**Pipeline** (`python -m scripts.ml.<name>`, run in this order):
1. `fetch_dem.py` — downloads Copernicus GLO-30 (AWS Open Data, no key) for
   the Sikkim tile, reprojects to UTM 45N (required for correct slope/aspect —
   verified: without reprojection, slope comes out ~90° everywhere)
2. `fetch_osm_roads.py` — Sikkim road network via Overpass API
3. `extract_terrain_features.py` — elevation/slope/aspect/curvature
   (`xarray-spatial`, Horn's method) + distance-to-drainage (`pysheds` D8
   flow accumulation)
4. `build_negative_samples.py` — road-corridor negative sampling (see below)
5. `build_training_dataset.py` — joins everything, prints a review summary,
   saves `data/processed/sampling_map.png`, writes
   `data/processed/training_dataset.csv`. **Does not train anything.**
6. `rainfall_threshold_case_study.py` — separate, see above

**Negative sampling method:** road corridor (500m buffer) minus a 200m
exclusion disc around every positive, further restricted per-district to
that district's own positives (preserves district proportions without
needing external admin boundaries) — buffer distances configurable in
`scripts/ml/ml_config.py`, seeded (`random_seed=42`) for reproducibility.

**Verified result** (this session): 777 positives / 777 negatives, exact
district-proportion match, minimum inter-class distance 203.7m (≥ the 200m
exclusion buffer). Positives show meaningfully higher mean slope (33.2° vs
28.4°) and more concave curvature than negatives — real, non-trivial signal,
not an artificially-easy split.

**Environment note:** `pyogrio`/`fiona` (geopandas' file-IO backends) are
blocked by this machine's Application Control policy (persistent, unlike an
earlier one-off `rasterio` block that cleared on retry) — worked around by
reading/writing GeoJSON directly via `json` + `shapely`, keeping GeoDataFrame
usage in-memory only. `pysheds` also needed a one-line `numpy.in1d` →
`numpy.isin` compatibility shim (numpy 2.x removed the old name) — not a
custom algorithm, just un-renaming a numpy function.

Tests: `tests/test_negative_sampling.py`, `tests/test_terrain_features.py` —
synthetic geometry/DEMs, no network or real data files needed, run fast.

## Seeding a pilot zone
`scripts/seed_zone.py` takes a GeoJSON Polygon file and a name — it does
**not** invent coordinates. `config/pilot_zone.example.geojson` is a
placeholder square in the Gulf of Guinea (obviously not a real place) showing
the expected file shape. Once Data/GIS lead has the real pilot zone boundary
from QGIS, export it as a Polygon GeoJSON and run:
```bash
python scripts/seed_zone.py path/to/real_zone.geojson "Gangtok pilot zone"
```

## Local setup
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp .env.example .env          # edit RAINFALL_THRESHOLD__* if the team finds/verifies a different source
```

Run the tests (no DB needed):
```bash
pytest tests/ -v
```

Start Postgres/PostGIS (needs Docker):
```bash
docker compose up -d
python scripts/migrate.py
```

Run the API:
```bash
uvicorn app.main:app --reload
```
Docs at http://localhost:8000/docs
