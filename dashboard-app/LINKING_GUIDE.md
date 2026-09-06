# LINKING GUIDE — where every teammate's work plugs into this frontend

This file is the single map of "who connects what, and where." It mirrors the
6-stage pipeline diagram. Everything the frontend needs is already built and
running on **mock data**, so nobody is blocked. When a stage is ready, follow
its section below.

Only **one file** needs to change for almost every hookup:
`src/services/api.js`. All mock data lives in `src/data/mockData.js`.

```
SIH_draft_6/
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

---

## LINK SPOT J — Admin profile (added in draft 3)
**Owner:** Backend team, once authentication exists
**Frontend hookup:** `src/components/AdminDrawer.jsx` → `getAdminProfile()` / `updateAdminProfile()` in `src/services/api.js`
**Suggested endpoints:** `GET {BASE_URL}/api/me` and `PATCH {BASE_URL}/api/me`
**What to send back:** the object shaped like `adminProfile` in `src/data/mockData.js`
(fullName, designation, department, employeeId, email, phone, district, region,
alertChannel, lastLogin, initials).

## LINK SPOT K — Verify a citizen report (added in draft 3)
**Owner:** Backend team
**Frontend hookup:** `src/components/CitizenReportModal.jsx` → `verifyCitizenReport(id)`
**Suggested endpoint:** `POST {BASE_URL}/api/citizen-reports/{id}/verify`
**What it should do:** set that report's status to `"Verified"`, and record which
officer verified it and when. Return `{ ok: true, id, status: "Verified" }`.

## LINK SPOT L — Incident report PDF (added in draft 3)
**Owner:** nobody yet — the frontend already does this on its own
**Frontend hookup:** `src/pages/Incidents.jsx` → `generateIncidentReport()` in `src/services/incidentReport.js`
The PDF is built in the browser with jsPDF from the incident record plus the
citizen reports for the same `area`. Nothing server-side is required.

If a signed / letterheaded / archived PDF is wanted later, add
`GET {BASE_URL}/api/incidents/{id}/report.pdf`, have the Download button fetch
that blob instead, and delete `incidentReport.js`. The button itself would not
change.

**Note on the incident record:** the PDF needs these extra fields on each
incident, on top of the original id/location/date/severity/status —
`area`, `weatherReport`, `rainfallTrend` (array of `{ day, mm }`), `areaHistory`
(array of strings), `casualties`, `infrastructureImpact`, `responseSummary`.
See the `incidents` mock in `src/data/mockData.js` for the exact shape.

---

## LINK SPOT M — Global search (added in draft 5)
**Owner:** Backend team
**Frontend hookup:** `src/components/SearchBox.jsx` → `searchAll(query)` in `src/services/api.js`
**Suggested endpoint:** `GET {BASE_URL}/api/search?q=mangan&limit=12`
**What to send back:** ONE merged array covering zones, alerts, incidents and
citizen reports:

```json
[
  {
    "id": "s-z1",
    "type": "Zone",
    "title": "Mangan, North Sikkim",
    "subtitle": "High risk · susceptibility 86%",
    "to": "/"
  }
]
```

`type` must be exactly `"Zone" | "Alert" | "Incident" | "Citizen report"` —
that decides which group the result appears under and what colour its tag is.
`to` is the frontend route to open when the result is clicked.
The search box, dropdown, grouping and keyboard navigation are already
finished; only this one function changes.

## LINK SPOT N — Notifications (added in draft 5)
**Owner:** Backend team + notifications team
**Frontend hookup:** `src/components/NotificationsPanel.jsx` →
`getNotifications()` and `markNotificationsRead()` in `src/services/api.js`
**Suggested endpoints:**
- `GET {BASE_URL}/api/notifications` → the signed-in officer's list
- `POST {BASE_URL}/api/notifications/read` → mark them all read

**What to send back:**

```json
[
  {
    "id": "NT-9",
    "title": "High risk raised for Mangan, North Sikkim",
    "detail": "Susceptibility 0.86 with 128 mm in the last 24 hours.",
    "severity": "High",
    "timeAgo": "2 min ago",
    "read": false,
    "to": "/alerts"
  }
]
```

**Depends on authentication.** `read` is per-officer, so this endpoint only
becomes meaningful once login exists. Until then the frontend shows the same
mock list to everyone, which is intentional and is stated in the panel and on
the Help page.
