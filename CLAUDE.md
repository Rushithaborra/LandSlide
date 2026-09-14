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

**Real forecast added, and a bug it would have caused pre-empted, 2026-09-14**:
PS26001 explicitly names "weather forecasts" as a dashboard requirement, and
this build had none — `open_meteo.fetch_daily_rainfall`'s `forecast_days=1`
turns out (verified directly against Open-Meteo's API) to mean "today only,"
not "tomorrow"; no genuinely future-dated day was ever being fetched at all.
Bumped `forecast_days` to 3 (today + the next 2 real days) to actually
deliver a forecast. Doing that immediately created the exact risk the fix
below guards against, so both landed together rather than the fetch change
going out first and the guard following later:
- `evaluate_daily_rainfall`'s `latest = max(daily_totals)` would otherwise
  anchor its backward-looking I-D windows on a *predicted* future day rather
  than today's confirmed data the moment forecast data with a real future
  date exists — meaning a real alert (and, now that Twilio is live, a real
  SMS/call) could fire off an unconfirmed forecast. Fixed with
  `alert_engine.drop_forecast_days()`, a small pure function filtering any
  date past today out of `check_and_trigger`'s dataset before evaluation —
  unit-tested directly (`tests/test_alert_engine.py`), including a test
  confirming a single huge forecast day alone cannot breach a threshold.
- `RainfallReadingOut` gained a computed `is_forecast` field (`app/schemas.py`,
  derived from the date being after today, no new DB column) so the
  dashboard's Rainfall Trend chart shows those 2 real forecast days distinctly
  (lighter bar + legend) instead of blending them into "observed" history.
  "Today" itself is deliberately never flagged as forecast — the alert engine
  needs to keep reacting to today's accumulating rain, not exclude it as
  unconfirmed, and that's also the more defensible rule to explain.

## Tech stack
- API: FastAPI (Python)
- DB: PostgreSQL + PostGIS (`docker-compose.yml` for local dev)
- Rainfall: Open-Meteo implemented and live-verified. Deck's tech-stack slide
  (8) lists IMD as primary with Open-Meteo/NASA GPM as fallback — in practice
  IMD API access wasn't reachable in the timeframe, so Open-Meteo is what's
  actually wired up. Keep this discrepancy visible to F (PM/pitch) rather than
  letting the deck imply IMD is live.
- Alerts: SMS/voice delivery is **real (Twilio, `app/services/sms_alerts.py`),
  integrated 2026-09-13 from teammate D's handover module, credentials set
  and live-verified 2026-09-14** — a real critical broadcast placed an
  actual phone call, `AlertBroadcast.status` came back `"sent"`. Trial
  account, so only manually-verified numbers actually receive anything.
  See "SMS & voice alerts" section below.

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

**Model trained and selected** (2026-09-02): 4 experiments (Logistic
Regression / Random Forest × baseline / extended features), evaluated on a
5-fold spatially-buffered block CV (2km cells, 200m buffer — see
`scripts/ml/spatial_cv.py`), never a naive random split. Best: Random
Forest + extended features, ROC-AUC 0.735 (spatial CV, not the inflated
naive-split number). Full methodology, diagnostics, and limitations in
`docs/model_training_report.md`. Artifacts in `data/models/`: fitted
pipeline (`susceptibility_model.joblib`), `validation_report.json`,
ROC/PR + feature-importance plots. `PUT /zones/{id}/susceptibility`
contract verified end-to-end against a real (placeholder) zone — no
backend changes needed, the model's output already matches the schema.
**Operationalized as a real road-corridor GIS layer** (2026-09-02):
`scripts/generate_zone_predictions.py` builds real prediction units from
actual OSM road geometry (768 filtered ways -> 3921 ~500m corridor
segments, 500m buffer reusing the existing negative-sampling constant),
extracts the same 5 features via zonal statistics (median for continuous,
dominant class for land cover), and predicts with the existing model --
no retraining. Output: `outputs/gis/sikkim_road_susceptibility.geojson`
(+ .csv). GeoPackage was attempted and is genuinely blocked here (pyogrio
Application Control policy, re-verified) -- documented, not worked around
with hand-rolled binary format code. `scripts/integrate_zone_predictions.py`
pushed all 3921 predictions into the live backend via the unmodified
`PUT /zones/{id}/susceptibility` -- caught and fixed a real bug in the
process (zone-name collisions from using a shared highway `ref` as the
match key silently overwrote ~52% of zones; fixed by embedding
`segment_id`). Full report: `docs/gis_prediction_layer.md`.

**Two-layer separation applies here too**: `rainfall_threshold_case_study.py`
validates the *existing* rainfall rule engine against 68 dated historical
events — it reuses `app.services.alert_engine.intensity_duration_threshold`
directly (not a duplicate copy) but its output never joins
`training_dataset.csv`. The susceptibility model must stay rainfall-free.

**Not yet done**: land cover / lithology features (roadmap-mentioned, not
sourced), and no model has been trained — dataset construction was
explicitly stopped for review before that step.

## Person B's real model — connected 2026-09-06 (supersedes most of the above for 3411 zones)
This directory's `scripts/ml/` pipeline above was groundwork built before
the actual ML lead (Person B) had started — a stand-in, not their real
deliverable. Person B's real, separate pipeline was discovered on the
`ml-integration` branch of this same repo: real DEM, real GSI inventory
(765 points), a RUSLE erosion model, real terrain rasters, trained into a
Random Forest (held-out AUC 0.774-0.782, plain 75/25 split — not the
spatially-buffered CV this directory's own model used, worth noting if
compared side by side). Their own `ml/api/README.md` said explicitly
"this is what Person C's backend calls" — that connection had never
actually been made. Now done: `scripts/ml_personB_integration/` (see its
own README) runs B's real model against every zone's centroid and pushes
results through the existing, unmodified `PUT /zones/{id}/susceptibility`
endpoint. **3411 of 3921 zones now carry B's real model** (`model_version:
personB-random_forest-v1-20260902`); the remaining 510 (mostly one road,
NH717A, extending past B's raster coverage) stayed on this directory's own
groundwork model (`random_forest-extended-v1-20260902`) rather than being
guessed. Both model versions are honestly distinguishable per-zone via
`GET /zones`.

Two other collaborator branches exist on this repo (`frontend-integration`,
and the merged `main`) — not yet inspected. Worth checking before the
internal round in case there's more real work sitting unconnected the same
way B's model was.

## NER expansion — phase 1 (architecture), 2026-09-13
The literal PS26001 wording is NER-wide; this build has been Sikkim-only.
Decided: stage the expansion, Assam and Mizoram next (chosen over Meghalaya/
Nagaland/Manipur/Arunachal Pradesh — both have a real, publicly-sourced
GSI-linked landslide inventory; Assam additionally has a real, citable
Guwahati rainfall intensity-duration equation, I = 5.9·D^-0.479, ISPRS
Archives 2014 — Nagaland/Manipur don't have confirmed public inventories).

**This phase makes the architecture multi-state-capable; it does NOT yet
add Assam's or Mizoram's real data** — that's substantial separate work
(sourcing each state's real GSI inventory is the hard part, the same as it
was for Sikkim) and is explicitly Phase 2/3, not done yet:

- `zones.state` column added (migration `004_zone_state.sql`), defaulted to
  `'Sikkim'` — all 3,921 existing real zones correctly backfilled, verified
  live. `GET /zones` and `GET /corridors` both take an optional `?state=`
  filter now.
- Rainfall thresholds are per-state (`app.config.get_rainfall_threshold`),
  not one global config. **Sikkim's threshold still lives in the original
  single `rainfall_threshold` field on purpose** — Render's live env vars
  already set it and this session can't edit Render's dashboard directly, so
  changing its name/shape would have silently broken production alerting.
  Assam's real Guwahati equation is added as a new, separate
  `rainfall_thresholds["assam"]` entry (see `.env.example`) —
  `verified_against_primary_text: false`, and its intensity unit (assumed
  mm/day) hasn't been independently confirmed either. Mizoram has no entry
  yet (no dedicated published equation found) — `check_and_trigger` skips
  alerting for any zone whose state has no configured threshold rather than
  borrowing another state's number.
- `scripts/ml/ml_config.py` has a `STATE_CONFIGS` registry now, but only
  `"sikkim"` is populated (pointing at the exact same real, verified DEM
  tile/bbox/UTM-45N values as before — zero behavior change). Assam/Mizoram
  are deliberately NOT stubbed with placeholder tile IDs/bboxes — see the
  comment in that file for exactly what Phase 2 needs to fill in for real
  (their correct UTM zone differs by longitude and must be re-derived, not
  copied from Sikkim's 45N).
- Dashboard has a state selector (`RegionContext`, `StateSelector.jsx` in the
  header) filtering the map, stat cards, and Highway Corridors. "All States"
  and "Sikkim" are functionally identical right now; Assam/Mizoram correctly
  show an honest empty state, not an error or fake data — verified live.

**Phase 2 (Assam) and Phase 3 (Mizoram), still to do:** source each state's
real GSI landslide inventory (the actual hard part), run `fetch_dem` /
`fetch_osm_roads` / terrain extraction / negative sampling / model training
for that state, generate and integrate its real zones, and — for Mizoram
only — find or adapt a real rainfall threshold.

## NER expansion — widened to all 8 states, 2026-09-14
Phase 1 above only made `zones.state` accept `'Sikkim'`, `'Assam'`,
`'Mizoram'` — every other real NER state would have needed its own schema
migration the day its real data was ready. Widened `zones.state`'s CHECK
constraint (`migrations/008_ner_all_states.sql`, plus the matching
declarative `CheckConstraint` in `app/models.py`) to all 8 real NER states:
Sikkim, Assam, Arunachal Pradesh, Manipur, Meghalaya, Mizoram, Nagaland,
Tripura. Dashboard's `NER_STATES` (`RegionContext.jsx`) widened to match, so
the state selector already lists all 8.

**Still only schema/UI scaffolding, same discipline as Phase 1** — this
does NOT add zones, DEM tiles, road bboxes, or rainfall thresholds for
Arunachal Pradesh/Manipur/Meghalaya/Nagaland/Tripura. `scripts/ml/
ml_config.py`'s `STATE_CONFIGS` still only has real entries for `"sikkim"`
and `"assam"` — inventing placeholder DEM tile IDs/bboxes/UTM zones for a
state whose real inputs haven't been sourced would risk a config that looks
complete but silently points at the wrong geography. Verified live:
3,921 zones unchanged, `GET /zones?state=Meghalaya` (and the other four
newly-allowed states) returns `[]`, not an error or fake data. The point of
this change is that sourcing any of these five states' real GSI inventory
and running the pipeline is now a pure data-and-config task — insert real
zone rows with the right `state` value, add a real `STATE_CONFIGS` entry
when that state's DEM/roads data is ready — with no further schema, API, or
dashboard changes needed first.

## Assam Phase 2 attempted, rolled back for now, 2026-09-14
Assam's real road-corridor pipeline was actually run this session
(`scripts/generate_zone_predictions.py`, same real OSM-road + terrain-feature
approach as Sikkim's): 66,677 real ~500m corridor segments, output at
`outputs/gis/assam_road_susceptibility.geojson` (+ `.csv`) — that source file
is untouched by the rollback below and is what re-integration will replay
against. `scripts/integrate_zone_predictions.py assam` bulk-inserted all
66,677 as real `Zone` rows, but the susceptibility PUT phase (writing each
zone's real model score via the same unmodified `PUT /zones/{id}/
susceptibility`) was interrupted after only 834 of 66,677 — the other 65,843
sat in production with `risk_tier IS NULL`.

**This surfaced a real, demonstrated production bug**, unrelated to Assam's
data quality: `GET /zones` and `GET /corridors` had no pagination and
computed each zone's centroid in Python (Shapely) on every request — already
a slow ~45-60s load at Sikkim's 3,921 zones, and a complete timeout once
66,677 more rows landed. Root-caused and fixed: stored `centroid_lat/lng`
columns computed once at insert time instead of per-request
(`migrations/009_zone_centroid_columns.sql`, backfilled and later made
`NOT NULL` in `migrations/010_zone_centroid_not_null.sql` once verified zero
NULL rows existed), `limit`/`offset` pagination with safe defaults
(`DEFAULT_ZONE_LIMIT=2000`, `MAX_ZONE_LIMIT=5000` in `app/routers/zones.py`),
sorting by the indexable `susceptibility_score` instead of a non-indexable
`risk_tier` CASE expression, and `load_only()` to stop hydrating the unused
`geometry` polygon column on every row — that last one was the dominant
cost, `/corridors?state=Assam` alone went from 21.5s to ~2s. Measured
before/after: Sikkim 45-60s → 1.5s, Assam (66,677 rows, unbounded) → 7s
capped. Deployed to Render.

That pagination default then broke the dashboard, which had been written
when "no limit" silently meant "everything": every `/zones` call in
`dashboard-app/src/services/api.js` was truncating Sikkim's real 3,921 zones
to 2000 on the map with no error. Fixed by having every call pass an
explicit `limit` matching the backend's own ceiling. That fix in turn
exposed two more real bugs, both fixed and deployed: `CACHE_TTL_MS` was
keyed by the literal string `"/zones"` but every call now carries a query
string, so the intended 10-minute cache silently never matched and every
page view was refetching from scratch; and switching the NER state selector
showed the newly-selected state's label next to the *previous* state's
real map/stats until the new fetch resolved (`Overview.jsx`,
`useAsyncData.js` now reset to a real loading state on an actual state/deps
change, while still not resetting on `useAlertStream`'s background
live-alert refresh, which must stay flash-free).

**Rolled back, 2026-09-14**: with only 834 of 66,677 Assam zones actually
scored, the other 65,843 unscored zones rendered on the map as ordinary
"Moderate" risk markers — `capitalizeTier(risk_tier)` in `api.js` defaults a
`null` tier to `"Moderate"`, visually indistinguishable from a real
assessment. That's a real honesty gap against this project's own "flag
simulated/unscored data clearly" rule, so rather than ship it, all 66,677
Assam `Zone` rows were deleted from production (verified first: zero
rainfall_readings/alerts/sms_alert_log/citizen_reports referenced them, so
nothing else was affected). `GET /zones?state=Assam` is back to `[]`, same
honest empty state as before Assam's data ever landed. Sikkim (3,921 zones,
fully scored) is unaffected and is the only state with real data again.

**To resume Assam properly**: re-run `scripts/integrate_zone_predictions.py
assam` (the source geojson is unchanged) and this time let the PUT phase
run to completion — or push scores in verified batches — before the zones
are visible in a state selectable from the dashboard. Also worth fixing
before any future partially-scored state goes live: `capitalizeTier`'s
`null → "Moderate"` fallback should be a distinct "not yet assessed" state,
not a silent stand-in for a real risk level.

## SMS & voice alerts — integrated 2026-09-13
Teammate D handed off a working `sms_alerts.py` module (Twilio) plus a
migration and a manual test script, packaged for a raw-psycopg2 backend. This
one is SQLAlchemy ORM throughout, so it needed real porting, not a drop-in:
DB access rewritten to ORM `select()`/models (`SmsAlertLog`,
`AuthorityContact` in `app/models.py`), the wrong table name (`reports` ->
`citizen_reports`) fixed, `zone_id` retyped `UUID` (was `TEXT`) in
`migrations/005_sms_alerts.sql`, and Twilio credentials moved into
`app.config.settings` (matching every other credential in this project)
instead of raw `os.environ.get()`.

**A real design bug the port surfaced**: the original gated phone calls on
`severity == "critical"`, but the automated rainfall engine only ever
produces `risk_tier` in `{low, moderate, high}` — there is no "critical" tier
there. "critical" only exists where a human picks it, in the Broadcast
composer (`AlertBroadcast.severity` / `BroadcastIn.severity`). Wired in as
originally suggested, the call-escalation branch would have been permanently
dead code. Fixed by wiring into the two places a severity actually comes
from, not one:
- `alert_engine.check_and_trigger()` -> `sms_alerts.trigger_zone_alert()`:
  automatic SMS to citizen subscribers using the zone's `risk_tier`. Sets
  `Alert.delivery_method` to the schema's existing (previously unused)
  `"sms_twilio"` value if a text actually sent, else stays `"log_only"`.
  Wrapped in try/except so a Twilio failure can never roll back an alert
  already committed to the DB — SMS is best-effort on top of a real alert,
  not a precondition for one.
- `routers/alerts.py:broadcast_alert()` -> `sms_alerts.escalate_critical_alert()`:
  real SMS (using the operator's own written message) when `"sms"` is one of
  the chosen `channels`, plus a real phone call to every `authority_contacts`
  row when `severity == "critical"` — regardless of whether `"sms"` was
  chosen, since a critical broadcast should escalate to a call either way.
  `AlertBroadcast.status` becomes `"sent"` only if a real send was attempted
  with Twilio configured; otherwise stays `"simulated"`, unchanged from before.

**Credentials set and live-verified 2026-09-14** (local `.env` and Render):
a real trial Twilio account, a purchased number, one manually-verified test
number, and a real `authority_contacts` row (`"Sushanth (Twilio test)"`,
`+918125710271`) — worth renaming/replacing with a real team contact before
the demo, or adding more real officials via the Authority Contacts page.
A live critical broadcast against production placed a real phone call and
came back `AlertBroadcast.status == "sent"`, confirmed by the recipient.
Trial-account limits still apply (see below) — full setup steps, the
function-by-function reference, and known limitations (Twilio trial
accounts only reach manually-verified numbers; subscriber list is
citizen-report phone numbers, not a real opt-in flow; no retry on failed
sends; English-only wording): `docs/sms_voice_alert_handover.md`.
Unit tests for the cooldown/severity-gating logic (everything DB/Twilio
mocked out): `tests/test_sms_alerts.py`.

## Testing
- `tests/test_alert_engine.py` — 12 passing unit tests against the pure
  decision core (`intensity_duration_threshold`, `evaluate_daily_rainfall`),
  no DB required. `check_and_trigger` (the DB-touching wrapper) still needs
  integration testing against a live Postgres.
- `tests/test_negative_sampling.py`, `tests/test_terrain_features.py`,
  `tests/test_spatial_cv.py`, `tests/test_generate_zone_predictions.py` —
  synthetic geometry/DEMs/rasters, no network or real data files needed.
- `tests/test_sms_alerts.py` — 9 tests against `sms_alerts.py`'s cooldown and
  severity-gating logic, every DB/Twilio call mocked out (no real Postgres or
  Twilio needed). All 50 tests pass together: `pytest tests/ -v`.

## Integration points to coordinate on
- ML lead (B): writes susceptibility scores via `PUT /zones/{id}/susceptibility`
- Frontend lead (D): reads `GET /zones`, `GET /rainfall/{zone_id}`, `GET /alerts`
- Reporting lead (E): submits via `POST /reports`, multipart/form-data —
  a `data` field (JSON string matching `CitizenReportIn`'s exact frontend
  field casing via aliases: reportType/severity/coords/placeName/etc.)
  plus an optional `photo` file, in one request. Matches what E's frontend
  already sends, reworked 2026-09-01. Photo storage moved to **Supabase
  Storage** (2026-09-02, see Deployment note below) — `photo_url` in the
  response is now a full, directly-viewable URL, no base-URL prefixing
  needed. Full contract: `docs/backend_api_for_E.md`.
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
Cloudflare quick tunnel (`bin/cloudflared.exe`, no account needed) — used
to unblock E (reporting frontend) on 2026-09-01 with a temporary URL.
**Superseded by permanent hosting (2026-09-02, see below)** — kept around
as a local-dev fallback only, not the URL E should be pointed at anymore.
`scripts/stop_public_dev_server.ps1` stops everything.

### Deployment — permanent hosting (2026-09-02)
Moving off this laptop onto **Supabase** (Postgres+PostGIS database, plus
**Supabase Storage** for citizen-report photos — a deployed host's own
filesystem is ephemeral, so photos can't live on local disk anymore) +
**Render** (the FastAPI app itself, via `render.yaml` Blueprint). Both
free-tier, no credit card, verified via live search this session. Full
step-by-step (clearly split into "user does this" account/dashboard steps
vs. "Claude does this" steps): `docs/deployment_guide.md`. Slim
deploy-only dependency list: `requirements-backend.txt` (verified against
every `app/**/*.py` import, install+import tested in a fresh venv).
`app.config.settings` gained `supabase_url` / `supabase_service_role_key`
/ `supabase_storage_bucket` (all `Optional`, so nothing breaks without
them set — `_save_photo()` in `app/routers/reports.py` raises a clear 500
only if a photo is actually uploaded without them configured). The old
local `/uploads` static mount is removed from `app/main.py`.
**Not yet live**: waiting on the user to create the Supabase project +
`citizen-reports` public bucket and a GitHub repo, at which point Claude
pushes and runs the migration against the real database — see
`docs/deployment_guide.md` Parts 1-4 for exact status.

`scripts/seed_zone.py` deliberately does not invent pilot-zone coordinates —
it takes a GeoJSON Polygon file. `config/pilot_zone.example.geojson` is an
obvious placeholder (Gulf of Guinea, not Sikkim) showing the expected shape;
swap in the real boundary once Data/GIS lead has it from QGIS.

`scripts/seed_zone.py` deliberately does not invent pilot-zone coordinates —
it takes a GeoJSON Polygon file. `config/pilot_zone.example.geojson` is an
obvious placeholder (Gulf of Guinea, not Sikkim) showing the expected shape;
swap in the real boundary once Data/GIS lead has it from QGIS.
