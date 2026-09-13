# Product Requirements Document — Landslide Early Warning System

**Team:** RESQ · **Problem Statement:** SIH26001 (AI-Based Early Warning and
Landslide Risk Monitoring System in NER) · **Theme:** Disaster Management ·
**Sponsoring Organization:** Ministry of Development of North Eastern Region
(MDoNER) · **Document status:** Living document, updated as the build changes ·
**Current build scope:** Sikkim (pilot state) · **Last updated:** 2026-09-13

---

## 1. Purpose

This document defines what the Landslide Early Warning System is for, who it
serves, what it does today (verifiable, live), and what it does not do yet
(explicitly deferred, not hidden). It is written to be checked against the
live system at any time — every claim below traces to a real endpoint, a
real number, or a real file in this repository, not an aspiration.

## 2. Problem Statement

The official problem statement (SIH26001) asks for an AI-based early warning
and landslide risk monitoring system for the North Eastern Region (NER) of
India. Two structural facts motivate this build:

- Landslides are concentrated in specific, known geography: ~12.6% of India's
  landmass is landslide-prone (GSI), and **Sikkim has the highest share of
  its own land area classified as landslide-susceptible of any Indian
  state.**
- No system today combines (a) where the ground is already structurally
  weak with (b) whether today's weather makes that weakness dangerous, in
  one live, checkable tool that both officials and citizens can use.

**Honest scope note:** the problem statement's literal scope is the whole
NER (8 states); this build is currently Sikkim-only, chosen as the pilot
state precisely because it has the strongest, most measurable case for
urgency. NER-wide expansion is planned next-phase work (§9), not silently
substituted for the full ask.

## 3. Goals

1. Score landslide susceptibility for real, specific locations from real
   terrain and historical-landslide data — not a generic hazard map.
2. Turn live rainfall into an automatic alert when it crosses a danger
   threshold for that specific location's susceptibility.
3. Let ordinary citizens report hazards from a phone and have that reach an
   officer's dashboard for verification in real time.
4. Do all of the above with total honesty about what is real, live, and
   verified versus what is mocked, planned, or simulated — no feature is
   ever presented as working when it isn't.

## 4. Target Users

| User | Need |
|---|---|
| **State disaster management officer** | See which roads/zones are at risk right now, verify citizen reports, issue a public warning |
| **Field officer / surveyor** | File a hazard report from the ground, from a phone, with a photo |
| **Citizen in a landslide-prone area** | Report a crack/slide they see; know when their area is under warning |
| **Ministry / policy stakeholder (MDoNER)** | See a working, replicable model for a pilot state before committing to NER-wide rollout |

## 5. Scope

### 5.1 In scope, live today
- **Static risk layer:** ML-scored susceptibility per zone (§6.1)
- **Dynamic risk layer:** rainfall intensity-duration alert rule (§6.2)
- **Citizen reporting:** submission, photo upload, officer verification (§6.3)
- **Officer tooling:** Highway Corridors view, Emergency Contacts directory,
  Alert Broadcast composer (§6.4)
- **Live deployment:** three real hosted services (§8)

### 5.2 Explicitly out of scope this round
- Real SMS/IVR/siren delivery (alerts and broadcasts are logged/simulated —
  see §6.2 and §6.4; a full delivery roadmap exists but is not built)
- Physical IoT sensors (soil moisture, pore pressure, inclinometers) — this
  system deliberately substitutes satellite DEM + terrain analysis instead
  of claiming a sensor network that doesn't exist
- Authentication / role-based access — open API, matches this round's scope
- AI-generated natural-language bulletins (e.g. an LLM writing SITREP text)
- NER-wide coverage (Sikkim only, by design — see §2)

## 6. Functional Requirements

### 6.1 Static susceptibility layer (ML-owned, offline)
- A trained Random Forest model scores every zone's landslide susceptibility
  from terrain features (slope, curvature, drainage, land cover, elevation,
  aspect, terrain ruggedness, rainfall climatology).
- Score and tier are written once via `PUT /zones/{id}/susceptibility` — the
  backend never computes this itself, only stores and serves it.
- **Live data (checked 2026-09-13):** 3,921 zones scored; 3,411 on the
  connected ML lead's model (held-out AUC 0.774–0.782), 510 on this team's
  own groundwork model (spatial-CV AUC 0.735) for zones outside the first
  model's raster coverage. Tier split: 806 high / 1,388 moderate / 1,727 low.

### 6.2 Dynamic rainfall alert layer (rule-based, backend-owned)
- Live rainfall (Open-Meteo) is checked against a published intensity-duration
  threshold (Harilal et al. 2019, Sikkim), scaled stricter for higher-tier
  zones (`SUSCEPTIBILITY_MULTIPLIERS`, this team's own explainable rule).
- An alert is written per breach, labeled explicitly as a landslide-risk
  event (e.g. *"High landslide-risk zone — 5-day rainfall averaged
  14.0mm/day, exceeding the 9.9mm/day danger threshold"*), not a bare
  rainfall number.
- **Live data:** 51 real alerts fired from real rainfall, all currently active.
- Delivery is logged only (`delivery_method=log_only`) — no real SMS yet.

### 6.3 Citizen reporting
- `POST /reports` accepts type, severity, coordinates or place name, photo,
  reporter contact — photo stored in Supabase Storage (not local disk, which
  is ephemeral on a deployed host).
- `POST /reports/{id}/verify` lets an officer mark a report verified from the
  dashboard.
- Real coordinates are shown on the report detail view (fixed from an
  earlier bug where this showed placeholder text).

### 6.4 Officer tooling (added 2026-09-12 to close feature-parity gaps)
- **Highway Corridors** (`GET /corridors`): the existing 3,921 zones grouped
  by the real highway code already embedded in each zone's name (NH10,
  NH310A, SH, etc.) — no new data source, a different view of existing data.
- **Emergency Contacts:** a static click-to-call directory. 112/108 shown
  with full confidence (real, nationwide, unambiguous); state/NDRF/BRO
  entries are honestly marked "unconfirmed — verify before real-world use"
  rather than presented as verified.
- **Alert Broadcast composer** (`POST /alerts/{id}/broadcast`): an officer
  composes a public warning (headline, severity, message, channels) and it
  is really persisted (`alert_broadcasts` table) — the confirmation banner
  states plainly that dispatch is simulated, no SMS/CAP/siren gateway exists
  yet.
- **One-touch SOS:** a `tel:112` link, always visible in the header.

## 7. Non-Functional Requirements

- **Honesty:** every simulated/mocked feature must be labeled as such in the
  UI itself, not only in code comments (established practice — see the
  broadcast confirmation banner, the Emergency Contacts "unconfirmed" tags,
  and `README.md`'s "Implemented / Simulated / Pending" section).
- **Resilience:** every page making a real backend call must show a real
  error + retry on failure, not hang or silently render empty (fixed
  2026-09-06 to 2026-09-07 after two real production incidents).
- **Performance:** `/zones` (3,921 rows, ~1.1MB) is cached client-side for 10
  minutes so repeated page views don't re-pay a multi-second fetch on
  Render's free tier.
- **Cost:** every service used is free-tier (Render, Vercel, Supabase,
  Open-Meteo) — zero licensing cost at this scale.

## 8. Live Deployment

| Service | URL | Host |
|---|---|---|
| Backend API | https://landslide-ews-backend.onrender.com | Render (free) |
| Officer dashboard | https://dashboard-app-ten-sooty.vercel.app | Vercel (free) |
| Citizen report app | https://land-slide-alpha.vercel.app | Vercel (free) |
| Database + storage | Supabase project (Postgres + PostGIS + Storage) | Supabase (free) |

Render's free tier sleeps after inactivity — warm `/health` before any demo.

## 9. Roadmap (Now → Next → Later)

- **Now (this build):** Sikkim, real susceptibility + rainfall alerting +
  citizen reporting + the officer tooling in §6.4.
- **Next:** real SMS/IVR delivery (roadmap already drafted — DLT-registered
  templates, MSG91/Exotel, CAP 1.2 emission for cell-broadcast compatibility
  with NDMA's Sachet system); resolve the Sikkim-vs-NER scope question with
  the PS owner.
- **Later:** NER-wide expansion (same pipeline, new state's DEM/GSI
  inventory/road network — architecture is state-agnostic already);
  authentication/role-based access; verify the rainfall threshold's
  coefficients against the primary paywalled text.

## 10. Assumptions & Constraints

- No physical sensor network exists or is assumed — all terrain signal comes
  from public satellite/survey data (Copernicus DEM, OpenStreetMap, GSI).
- No institutional data-sharing agreement exists with IMD; Open-Meteo is the
  live rainfall source (the deck's tech-stack slide names IMD as the
  eventual primary source).
- No authentication exists; this is an accepted, documented gap for this
  round, not an oversight to be found later.
