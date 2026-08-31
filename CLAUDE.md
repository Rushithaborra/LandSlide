# Landslide Early Warning System — Backend

This file is read automatically by Claude Code at the start of every session
in this directory.

## Project context
4-day internal-round hackathon build for SIH 2026, Problem Statement 26001
(Disaster Management). Pitch deck is finalized (`docs/landslide_ews_pitch.pptx`,
11 slides). This directory is **backend only** — role: Team Member C, Backend
Lead. Full team context: `docs/landslide-ews-roadmap.pdf` (differentiation
strategy, Q&A prep) and `docs/internal-round-4day-plan.pdf` (this round's
2-feature team split).

## Scope discipline
Team deliberately scoped to **2 features**, built deep instead of 6 shallow:
1. Susceptibility Model + GIS Heatmap (Data/GIS lead + ML lead)
2. Real-Time Alerts + Citizen Reporting (backend plugs in here)

Everything else (sensors, native mobile, full multilingual SMS, IMD MoU,
pan-NER expansion) is the documented "Roadmap — Next Phase" on slide 9 of the
deck — do not suggest pulling any of it into this build.

## My role: Backend (C)
| Days | Deliverable |
|---|---|
| 1-2 | API + DB schema, rainfall API integration |
| 3-4 | Alert trigger logic (rainfall-threshold → alert fire) |

### "Done" bar for Day 4
- API serves the ML lead's real trained-model output (backend doesn't compute it)
- Dashboard reads real data from this API, not a mockup
- One alert fires live during rehearsal from a real or simulated rainfall value
- One citizen report flows form → backend → dashboard, live

## Two-layer risk logic — keep conceptually separate (a pitch talking point, slide 4)
- **Static (ML):** `zones.susceptibility_score` / `risk_tier`, written by the
  ML lead's pipeline via `PUT /zones/{id}/susceptibility`. Backend reads/serves,
  never computes.
- **Dynamic (rules, backend-owned):** rainfall intensity-duration threshold in
  `app/services/alert_engine.py`. Must stay literature-sourced (see roadmap doc
  §4) and explainable — never dressed up as ML. Honest answer to "is this AI or
  rules?": two layers, named separately on purpose.

## Tech stack
- API: FastAPI (Python)
- DB: PostgreSQL + PostGIS (`docker-compose.yml` for local dev)
- Rainfall: Open-Meteo implemented and live-verified. Deck's tech-stack slide
  (8) lists IMD as primary with Open-Meteo/NASA GPM as fallback — in practice
  IMD API access wasn't reachable in the timeframe, so Open-Meteo is what's
  actually wired up. Keep this discrepancy visible to F (PM/pitch) rather than
  letting the deck imply IMD is live.
- Alerts: SMS delivery is **not implemented** — alerts are logged
  (`delivery_method="log_only"`) per the Honesty Rule below. Twilio/MSG91
  sandbox is a stretch goal only if trivial.

## Data model
`migrations/001_schema.sql`: `zones` (PostGIS geometry, susceptibility_score,
risk_tier), `rainfall_readings`, `alerts`, `citizen_reports`.

## Integration points to coordinate on
- ML lead (B): writes susceptibility scores via `PUT /zones/{id}/susceptibility`
- Frontend lead (D): reads `GET /zones`, `GET /rainfall/{zone_id}`, `GET /alerts`
- Reporting lead (E): submits via `POST /reports` — this API takes a
  `photo_url` string only, does not host the upload itself
- PM/pitch lead (F): needs the real validation number (deck slide 5 still has
  the placeholder `[AUC / accuracy on held-out points]` — do not invent it)
  and current real-vs-simulated status (deck slide 9) kept accurate

## Honesty rule
If something is simulated/mocked (SMS delivery, IMD data, a citizen report),
flag it clearly rather than letting it silently look real in the demo. See
`README.md` "What's real vs. simulated" for current status — keep that section
up to date as things change.

## Environment notes
No Docker or local Postgres/psql available as of the last session in this
environment — DB-backed endpoints are written but unverified against a live
DB. `docker-compose.yml` targets `postgis/postgis:16-3.4`; run
`docker compose up -d && python scripts/migrate.py` on a machine with Docker,
then re-verify.
