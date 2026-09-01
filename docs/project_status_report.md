# Project Status Report — Landslide EWS

SIH 2026, Problem Statement 26001. Covers backend (my primary role, Team Member C) plus the ML/data groundwork this directory took on for the susceptibility model. Generated 2026-09-01.

## Scope reminder

Two features, built deep instead of six shallow (documented team decision):
1. **Susceptibility Model + GIS Heatmap** — Data/GIS lead (A) + ML lead (B), backend serves it
2. **Real-Time Alerts + Citizen Reporting** — backend-owned

---

## Feature 1 — Susceptibility Model + GIS Heatmap

### Completed
- **Real landslide inventory**: 777 GSI-verified Sikkim landslide records extracted and audited (coordinates, dates, duplicates all checked)
- **Real DEM**: Copernicus GLO-30 sourced, verified, correctly reprojected (caught a real bug — unreprojected data gave nonsense slope values)
- **Terrain features implemented and tested**: elevation, slope, curvature, distance-to-drainage
- **Land cover integrated**: ESA WorldCover, real signal found (built-up land is 30× more common at landslide sites than elsewhere)
- **Negative (non-landslide) samples**: built with a defensible road-corridor method, not naive random points — tested, reproducible, documented
- **Supplementary data collected**: soil composition, population, boundaries, road/village/building layers — broad collection pass across the team's full data checklist (27 items), each one verified accessible or explicitly logged as unavailable
- **Lithology (rock type) assessed and correctly excluded** — the only available source is far too coarse to be useful at our scale; documented rather than forced in
- **Final training dataset built and reviewed**: 1554 balanced rows, checked for missing values, duplicate coordinates, and data leakage — clean
- **Rainfall-history case study**: 68 real historical landslide events checked against actual weather records (kept as a separate validation exercise, not mixed into the susceptibility data)

### Remaining
- **No model has been trained yet** — this is the single biggest remaining item. Data is ready; training itself has not started, pending final go-ahead
- **No validation number exists yet** (accuracy/AUC) — the pitch deck's slide 5 placeholder is still unfilled; must come from real training, not be invented
- **Real pilot zone boundary** not yet loaded into the database — waiting on Data/GIS lead's QGIS output (script is ready, deliberately doesn't invent coordinates)
- **GIS heatmap dashboard** — Frontend lead's build, not this directory's work; backend is ready to serve data once a model exists
- A few secondary soil/terrain properties are extracted and available but deliberately held out of the first model (kept simple and defensible first, can be added for comparison later)

---

## Feature 2 — Real-Time Alerts + Citizen Reporting

### Completed
- **Backend API built**: zones, rainfall, alerts, citizen reports — all core endpoints working
- **Live rainfall data**: connected to a real weather source, both current and historical
- **Alert rule engine**: the rainfall threshold that triggers an alert is based on a real published research paper (not invented), combined with each zone's landslide-risk level — 12 automated checks confirm it behaves correctly
- **Citizen reporting form connection**: backend reworked to match the reporting form's exact data format, including photo upload handling (this didn't exist before) and safe handling of repeated/offline submissions
- **Real database stood up**: previously the backend had never been tested against a real database — that's now fixed, running locally without needing Docker
- **Public test link for the reporting team**: set up so the citizen-reporting form can be tested from a different device, verified working end-to-end including a real photo upload

### Remaining
- **SMS delivery not implemented** — alerts are logged, not texted out; explicitly scoped as optional and only worth doing if time allows
- **No alert has fired live in a full rehearsal yet** — needs a zone with a real risk score first (depends on Feature 1's model existing)
- **Dashboard side of the citizen-report flow** not yet confirmed — backend and the report form are proven working together; whether the dashboard displays it live is Frontend lead's side to confirm
- **The public test link is temporary** — it changes each time it's restarted; a stable link for the actual demo day is a decision still to be made
- A couple of test submissions are currently sitting in the live database from verification testing — harmless, but worth clearing before a real demo

---

## Backend infrastructure (cross-cutting)

### Completed
- FastAPI backend running, all endpoints implemented
- Real database (Postgres + PostGIS) running locally for the first time this project
- 24 automated tests, all passing
- No account/API-key dependencies anywhere in the pipeline — everything runs on free, open access

### Remaining
- No login/authentication on any endpoint — intentionally out of scope for this round
- No decision yet on where this runs for the actual demo (this laptop, or a real hosted deployment)
- Systematic error-handling/integration testing across all endpoints together hasn't been done as a dedicated pass (individual pieces tested, not the whole system under stress)

---

## Day 4 "done" checklist (from the internal team plan)

| Item | Status |
|---|---|
| API serves the ML lead's real trained-model output | API ready and waiting; no trained model yet |
| Dashboard reads real data from this API, not a mockup | Backend ready; dashboard side unconfirmed (Frontend lead) |
| One alert fires live during rehearsal | Not yet — needs a scored zone first |
| One citizen report flows form → backend → dashboard, live | Backend + form proven; dashboard leg unconfirmed |

---

## Priority order for what's left

1. **Train the susceptibility model** (data is ready and reviewed) — unblocks the real validation number and the heatmap
2. **Get the real pilot zone boundary** from Data/GIS lead, seed it into the database
3. **Run one full live alert rehearsal** once a zone has a real score
4. **Confirm the dashboard is actually pulling live data**, not a mockup
5. **Decide on a stable hosting approach** for demo day (this machine vs. real deployment)
