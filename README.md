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

**Pending — needs a live Postgres/PostGIS instance (none available in this
environment tonight):**
- Applying `migrations/001_schema.sql`
- Verifying `/zones`, `/rainfall`, `/reports`, `/alerts` end-to-end
- Running `scripts/seed_zone.py` for real (needs both a DB and a real pilot
  zone boundary — see below)
- A true "alert fires live" rehearsal against real ingested data

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
