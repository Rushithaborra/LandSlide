# Landslide Early Warning System — Backend

This file is read automatically by Claude Code at the start of every session
in this directory.

## Project context
4-day internal-round hackathon build for SIH 2026, Problem Statement 26001
(Disaster Management). Pitch deck is finalized (`docs/landslide_ews_pitch.pptx`,
11 slides). Primary role: Team Member C, Backend Lead — but this directory
has also taken on the Sikkim data audit and ML data pipeline (`scripts/ml/`)
this session, since that groundwork (real GSI inventory, real DEM, defensible
negatives) has to exist before the ML lead's model training can start. Full
team context: `docs/landslide-ews-roadmap.pdf` (differentiation strategy, Q&A
prep) and `docs/internal-round-4day-plan.pdf` (this round's 2-feature team
split).

## Scope discipline
Team deliberately scoped to **2 features**, built deep instead of 6 shallow:
1. Susceptibility Model + GIS Heatmap (Data/GIS lead + ML lead)
2. Real-Time Alerts + Citizen Reporting (backend plugs in here)

Everything else (sensors, native mobile, full multilingual SMS, IMD MoU,
pan-NER expansion) is the documented "Roadmap — Next Phase" on slide 9 of the
deck — do not suggest pulling any of it into this build.

## Coding philosophy — library-first, minimal-code
Before writing custom code for anything nontrivial, ask "does an established,
well-maintained library already solve this?" and prefer that over hand-rolled
logic — especially for validation/schema handling, HTTP, DB ops, geospatial
work, raster/DEM processing, ML preprocessing/training, testing, config, and
serialization. Concretely:
- Prefer FastAPI/Pydantic/SQLAlchemy/GeoAlchemy2/Shapely/httpx/pytest (already
  in this project) over custom equivalents; check existing dependencies before
  adding a new one, and don't add one to save a couple of lines.
- **Do not hand-roll scientific/geospatial/ML algorithms** when scikit-learn,
  GeoPandas, Shapely, Rasterio, etc. already provide them — the roadmap itself
  specifies QGIS/Python and scikit-learn logistic regression/random forest for
  exactly this reason. Defensible, reproducible engineering over clever code.
- Keep functions small and reusable; remove dead code, unused imports,
  duplicate validation, and redundant DB/API calls as you go.
- This is an SIH prototype — simplest production-sensible solution, not
  over-engineered, but never sacrifice correctness for fewer lines.
- Priority order: **correctness → security → maintainability → readability →
  simplicity → line count.**
- Before calling any task done, do a quick pass: can this be simpler? is
  anything duplicated or unused? does an existing dependency make this
  cleaner? would removing an abstraction help? Then re-run the relevant tests.

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
- **Static (ML):** `zones.susceptibility_score` / `risk_tier` / `model_version`,
  written by the ML lead's pipeline via `PUT /zones/{id}/susceptibility`.
  Backend reads/serves, never computes.
- **Dynamic (rules, backend-owned):** rainfall intensity-duration (I-D)
  threshold in `app/services/alert_engine.py`, loaded from
  `app.config.settings.rainfall_threshold` (config-driven, no hardcoded
  number — see `.env.example`). Currently sourced from Harilal et al. (2019),
  *Landslides* 16(12), DOI 10.1007/s10346-019-01244-1, a Sikkim-specific
  paper — **not yet verified against the primary text** (paywalled), flagged
  via `verified_against_primary_text: false`. Verify or replace before
  quoting it to judges.
- The two layers **combine**: `SUSCEPTIBILITY_MULTIPLIERS` in `alert_engine.py`
  scales the I-D threshold by the zone's `risk_tier` (high-susceptibility
  zones alert at a lower rainfall bar). This multiplier table is the team's
  own explainable rule, not literature-sourced — say so if asked.
- Honest answer to "is this AI or rules?": two layers, named separately on
  purpose. Never dress the rainfall-trigger layer up as ML.

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
risk_tier, model_version), `rainfall_readings`, `alerts`, `citizen_reports`.

## ML data pipeline (`scripts/ml/`) — susceptibility model groundwork
**Scope is intentionally road-corridor, not full-state** — the GSI Sikkim
inventory is 96.1% within 100m of a mapped road (measured, not assumed),
a field-survey artifact. Sampling negatives from the same corridor (not
uniformly across Sikkim) avoids the model learning "distance to road" as a
shortcut instead of real terrain signal, and this scope choice matches the
project's own road-connectivity framing rather than hiding a limitation.
See README.md "ML data pipeline" section for the full pipeline order,
verified results (774/774 pos/neg after resolving 3 duplicate-coordinate
positives, min inter-class distance 203.7m, real slope signal 33.2° vs
28.4°), the land-cover bias audit (built-up carries signal beyond simple
road proximity, but the mechanism — genuine anthropogenic destabilization
vs. GSI's own documentation priority — can't be fully separated), and two
environment workarounds worth knowing about before touching this code: a
`pyogrio`/`fiona` DLL block (worked around via plain-JSON GeoJSON I/O) and
a `pysheds`/numpy 2.x incompatibility (one-line `np.in1d = np.isin` shim).

**Two candidate feature sets awaiting training approval** (not trained
yet): Baseline (elevation, slope, curvature, distance_to_drainage) vs
Extended (baseline + land_cover_class) — train both, compare on the same
spatially-defensible holdout, per explicit instruction not to just trust
the bigger feature set.

**Two-layer separation applies here too**: `rainfall_threshold_case_study.py`
validates the *existing* rainfall rule engine against 68 dated historical
events — it reuses `app.services.alert_engine.intensity_duration_threshold`
directly (not a duplicate copy) but its output never joins
`training_dataset.csv`. The susceptibility model must stay rainfall-free.

**Not yet done**: land cover / lithology features (roadmap-mentioned, not
sourced), and no model has been trained — dataset construction was
explicitly stopped for review before that step.

## Testing
- `tests/test_alert_engine.py` — 12 passing unit tests against the pure
  decision core (`intensity_duration_threshold`, `evaluate_daily_rainfall`),
  no DB required. `check_and_trigger` (the DB-touching wrapper) still needs
  integration testing against a live Postgres.
- `tests/test_negative_sampling.py`, `tests/test_terrain_features.py` — 12
  passing tests against synthetic geometry/DEMs (no network, no real data
  files needed). Together: 24 tests, `pytest tests/ -v`.

## Integration points to coordinate on
- ML lead (B): writes susceptibility scores via `PUT /zones/{id}/susceptibility`
- Frontend lead (D): reads `GET /zones`, `GET /rainfall/{zone_id}`, `GET /alerts`
- Reporting lead (E): submits via `POST /reports`, multipart/form-data —
  a `data` field (JSON string matching `CitizenReportIn`'s exact frontend
  field casing via aliases: reportType/severity/coords/placeName/etc.)
  plus an optional `photo` file, in one request. Backend now hosts the
  upload itself (saves to `uploads/`, served at `/uploads/<file>`) —
  matches what E's frontend already sends, reworked 2026-09-01.
- PM/pitch lead (F): needs the real validation number (deck slide 5 still has
  the placeholder `[AUC / accuracy on held-out points]` — do not invent it)
  and current real-vs-simulated status (deck slide 9) kept accurate

## End-of-session summary (do this every session, unprompted)
Before ending each session, give:
1. **What changed** — files touched, features/endpoints added or modified, tests run and their result.
2. **Tech/framework rundown** — every library or framework touched this session and *why* it was the right choice (not just named — the reasoning), so the user can defend each choice under jury Q&A without re-deriving it live. Tie back to the roadmap's own stated tech choices (`docs/landslide-ews-roadmap.pdf` §4, deck slide 8) where relevant.
3. **Current implemented/simulated/pending status** — pull from README.md, flag anything that changed since last session.
4. **Anything a judge could plausibly ask about** that this session touched — a new citation, a new assumption, a new simplification — phrased as a likely question + the honest answer, matching the roadmap's own Jury Q&A prep style (§5).
Keep it tight — this is Q&A ammunition, not a changelog dump.

## Honesty rule
If something is simulated/mocked (SMS delivery, IMD data, a citizen report),
flag it clearly rather than letting it silently look real in the demo. See
`README.md` "What's real vs. simulated" for current status — keep that section
up to date as things change.

## Environment notes
No Docker available in this environment, so instead of `docker-compose.yml`
(`postgis/postgis:16-3.4`, still the documented path on a machine that has
Docker), this machine runs a **native, no-installer Postgres 18 + PostGIS
3.6** in `bin/pgsql` (binaries-only zip from EDB + the OSGeo PostGIS bundle
copied on top — no admin rights needed, unlike the MSI installer). Data
directory: `bin/pgdata`. `bin/` is gitignored (1.3GB+, machine-specific).

**All DB-backed endpoints are now verified against this live database** —
migration applied for real, `/reports` tested end-to-end (real insert, real
photo saved to disk, real retrieval), not just import-checked.

`scripts/run_public_dev_server.ps1` starts Postgres + the backend + a
Cloudflare quick tunnel (`bin/cloudflared.exe`, no account needed) so a
teammate on another device/network can hit a real public URL — used to
unblock E (reporting frontend) on 2026-09-01. **The tunnel URL is ephemeral
and changes on every restart** — see `docs/backend_api_for_E.md` for the
current URL and full API contract. `scripts/stop_public_dev_server.ps1`
stops everything.

`scripts/seed_zone.py` deliberately does not invent pilot-zone coordinates —
it takes a GeoJSON Polygon file. `config/pilot_zone.example.geojson` is an
obvious placeholder (Gulf of Guinea, not Sikkim) showing the expected shape;
swap in the real boundary once Data/GIS lead has it from QGIS.

`scripts/seed_zone.py` deliberately does not invent pilot-zone coordinates —
it takes a GeoJSON Polygon file. `config/pilot_zone.example.geojson` is an
obvious placeholder (Gulf of Guinea, not Sikkim) showing the expected shape;
swap in the real boundary once Data/GIS lead has it from QGIS.
