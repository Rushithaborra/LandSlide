# Landslide EWS — Backend

FastAPI + PostgreSQL/PostGIS backend for the SIH 2026 (PS 26001) prototype.
Backend scope only: API, DB schema, rainfall ingestion, rule-based alert
trigger, citizen report intake. See `CLAUDE.md` for full project brief, and
`docs/` for the team roadmap, the internal 4-day plan, and the pitch deck.

## Two-layer risk model
- **Static (ML-owned):** `zones.susceptibility_score` / `risk_tier` — written
  via `PUT /zones/{id}/susceptibility` by the ML lead's pipeline. Backend
  reads/serves it, never computes it.
- **Dynamic (rules, this backend's job):** `app/services/alert_engine.py`
  checks rainfall intensity against `RAINFALL_ALERT_THRESHOLD_MM_PER_HOUR`
  (see `app/config.py`) and fires an `Alert` row. Rule-based on purpose —
  **the threshold constant is a placeholder, not a cited value.** Swap it for
  the team's literature-sourced intensity-duration threshold before the demo.

## What's real vs. simulated (keep this current for the pitch deck)
- Rainfall source: **Open-Meteo**, live, free, no key — confirmed working.
  IMD is the deck's named "real" source but out of reach in 4 days.
- SMS delivery: **not implemented.** Alerts are written to the `alerts`
  table and printed to the server log only (`delivery_method="log_only"`).
  Wire up Twilio sandbox if there's time; otherwise flag this on the honest-
  scoping slide.
- Citizen report photo upload: this API accepts a `photo_url` string only —
  it does not host file uploads. Reporting lead's form needs to upload the
  photo somewhere (e.g. Supabase/S3 bucket) and pass the resulting URL.

## Local setup
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp .env.example .env          # edit DATABASE_URL if not using docker-compose
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

## Status (2026-08-31)
- [x] FastAPI skeleton boots, `/health` and OpenAPI docs verified locally
- [x] Open-Meteo call verified live (returns hourly precipitation mm)
- [x] Schema written (`migrations/001_schema.sql`), migration script written
- [ ] Schema **not yet applied** — no local Postgres/Docker available in this
      session; run `docker compose up -d && python scripts/migrate.py` on a
      machine with Docker, then re-verify the DB-backed endpoints
- [ ] Alert trigger logic written, not yet exercised against a live DB
- [ ] Citizen report flow written, not yet exercised end-to-end
