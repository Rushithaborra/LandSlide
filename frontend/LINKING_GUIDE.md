# LINKING GUIDE — where every teammate's work plugs into this frontend

This file is the single map of "who connects what, and where." It mirrors the
6-stage pipeline diagram. Everything the frontend needs is already built and
running on **mock data**, so nobody is blocked. When a stage is ready, follow
its section below.

Only **one file** needs to change for almost every hookup:
`src/services/api.js`. All mock data lives in `src/data/mockData.js`.

```
SIH_draft_2/
└── src/
    ├── data/mockData.js     ← fake sample data (safe to delete once live)
    ├── services/api.js      ← EVERY backend hookup point (edit this file)
    ├── components/          ← visual pieces (map, cards, charts, tables)
    ├── pages/                ← one file per sidebar page
    └── layouts/DashboardLayout.jsx
```

---

## Stage A — Raw Spatial Data Ingestion (DEM rasters, GSI points, Sentinel-2, rainfall APIs)
**Owner:** Data engineering team
**Frontend hookup:** `src/pages/DataObservations.jsx` → `getDataSources()` in `src/services/api.js`
**Suggested endpoint:** `GET {BASE_URL}/api/system/data-sources`
**What to send back:** an array of `{ name, status, lastSync }` — see the
`dataSources` mock in `src/data/mockData.js` for the exact shape.

## Stage B — GIS Pre-processing & Feature Engineering (QGIS/Python)
**Owner:** GIS/ML team
**Frontend hookup:** none directly — this stage feeds Stage C. No UI change needed here.

## Stage C — Two-Tier Risk Modeling & Scoring (Scikit-Learn + rule engine, fused)
**Owner:** ML team
**Frontend hookup:** `src/pages/Overview.jsx` + `src/pages/LiveMap.jsx` → `getRiskZones()`
**Suggested endpoint:** `GET {BASE_URL}/api/risk-zones?region=sikkim`
**What to send back:** array of `{ id, name, lat, lng, level, susceptibility }`
where `level` is `"High" | "Moderate" | "Low"` and `susceptibility` is 0–1.
This is what colors the heatmap dots on the map.

## Stage D — Spatial Database & API Storage (PostgreSQL + PostGIS + FastAPI)
**Owner:** Backend team
**Frontend hookup:** almost everything in `src/services/api.js` — this is the
team that actually stands up the FastAPI server the other functions call.
**Suggested endpoints:**
- `GET /api/overview/summary` → `getSummaryStats()`
- `GET /api/alerts/active` → `getActiveAlerts()`
- `GET /api/alerts/recent` → `getRecentAlerts()`
- `GET /api/rainfall/trend` → `getRainfallTrend()`
- `GET /api/incidents` → `getIncidents()`

## Stage E — Notification & Alert Dispatch (Twilio / MSG91 / push)
**Owner:** Notifications team
**Frontend hookup:** `src/pages/Alerts.jsx` and the "Active Alerts" panel on
Overview read from the same `getActiveAlerts()` / `getRecentAlerts()` calls
above — dispatch itself (SMS/push) happens server-side and does not need a
frontend hook, but if you add an in-app "Send test alert" button later, wire
its POST call into `src/services/api.js` the same way the others are done.

## Stage F — Client Delivery: Citizen Reporting Form / PWA
**Owner:** Mobile/PWA team
**Frontend hookup:** `src/pages/CitizenReports.jsx` → `getCitizenReports()` and `submitCitizenReport()`
**Suggested endpoints:**
- `GET  /api/citizen-reports`
- `POST /api/citizen-reports` (multipart form: `location`, `note`, `lat`, `lng`, `photo`)

---

## How to actually flip a mock function to a real one

Open `src/services/api.js`, find the function (each has a `LINK SPOT` comment
block above it), and replace the body. Example for `getSummaryStats`:

```js
// BEFORE (mock)
export async function getSummaryStats() {
  return fakeDelay(summaryStats);
}

// AFTER (real backend)
export async function getSummaryStats() {
  const res = await fetch(`${BASE_URL}/api/overview/summary`);
  if (!res.ok) throw new Error("Failed to load summary stats");
  return res.json();
}
```

No page component needs to change — they already call `getSummaryStats()`
and just render whatever comes back.

## Environment setup for the real backend URL

```bash
cp .env.example .env
# then edit .env and set:
# VITE_API_BASE_URL=https://your-real-backend-url.com
```

Restart the dev server after editing `.env` (Vite only reads env files on startup):

```bash
npm run dev
```

---

## LINK SPOT I — Scrolling warning ticker (added in draft 2)
**Owner:** Notifications team (same team as Stage E)
**Belongs to:** Stage 5 — Notification & Alert Dispatch
**Frontend hookup:** `src/layouts/DashboardLayout.jsx` → `getTickerBulletins()` in `src/services/api.js`
**Rendered by:** `src/components/AlertTicker.jsx` (appears on every page)
**Suggested endpoint:** `GET {BASE_URL}/api/bulletins/ticker`
**What to send back:**

```json
[
  {
    "id": "TK-1",
    "severity": "High",
    "text": "Isolated extremely heavy rainfall likely over North Sikkim during 03rd-05th September.",
    "issuedAt": "issued 03 Sep, 08:30 IST"
  }
]
```

`severity` must be exactly `"High" | "Moderate" | "Low"`. `text` should be one
plain sentence with no HTML. The frontend refreshes this every 5 minutes
(`TICKER_REFRESH_MS` in `src/layouts/DashboardLayout.jsx`).
