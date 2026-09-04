/**
 * ============================================================================
 *  API SERVICE LAYER  —  THIS IS THE ONLY FILE THE BACKEND TEAM SHOULD EDIT
 * ============================================================================
 * Every function below is a "socket" the frontend already plugs into.
 * Right now each one returns MOCK data (imported from `src/data/mockData.js`)
 * wrapped in a fake network delay, so the UI works end-to-end today.
 *
 * TO GO LIVE: replace the body of a function with a real `fetch()` call to
 * the matching FastAPI endpoint from the pipeline diagram. Do not rename the
 * exported function or change what it returns — the pages already expect
 * this exact shape.
 *
 * Set VITE_API_BASE_URL in a .env file once the backend is deployed
 * (see .env.example in the project root).
 * ============================================================================
 */

import {
  summaryStats,
  activeAlerts,
  recentAlerts,
  rainfallTrend,
  riskZones,
  citizenReports,
  incidents,
  dataSources,
  tickerBulletins,
} from "../data/mockData";

// Used inside the TODO(backend) examples in each function below once real
// fetch() calls replace the mock returns.
// eslint-disable-next-line no-unused-vars
const BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

// Small helper so every mock call "feels" like a real network request.
const fakeDelay = (data, ms = 300) =>
  new Promise((resolve) => setTimeout(() => resolve(data), ms));

/* ----------------------------------------------------------------------- *
 * LINK SPOT A — Stage 4: Spatial Database & API Storage (PostgreSQL+PostGIS/FastAPI)
 * Owner: Backend team
 * Real endpoint (suggested): GET {BASE_URL}/api/overview/summary
 * Expected JSON shape: same as `summaryStats` in mockData.js
 * ----------------------------------------------------------------------- */
export async function getSummaryStats() {
  // TODO(backend): replace with:
  // const res = await fetch(`${BASE_URL}/api/overview/summary`);
  // return res.json();
  return fakeDelay(summaryStats);
}

/* ----------------------------------------------------------------------- *
 * LINK SPOT B — Stage 3 + Stage 5: Risk Engine Fusion -> Notification & Alert Dispatch
 * Owner: ML/backend team (risk scoring) + notifications team (Twilio/MSG91)
 * Real endpoint (suggested): GET {BASE_URL}/api/alerts/active
 * ----------------------------------------------------------------------- */
export async function getActiveAlerts() {
  // TODO(backend): const res = await fetch(`${BASE_URL}/api/alerts/active`);
  return fakeDelay(activeAlerts);
}

/* ----------------------------------------------------------------------- *
 * LINK SPOT C — Historical alert log, same source as Link Spot B
 * Real endpoint (suggested): GET {BASE_URL}/api/alerts/recent?limit=20
 * ----------------------------------------------------------------------- */
export async function getRecentAlerts() {
  return fakeDelay(recentAlerts);
}

/* ----------------------------------------------------------------------- *
 * LINK SPOT D — Stage 1: Live Rainfall APIs (IMD / Open-Meteo)
 * Owner: Data ingestion team
 * Real endpoint (suggested): GET {BASE_URL}/api/rainfall/trend?days=7
 * ----------------------------------------------------------------------- */
export async function getRainfallTrend() {
  return fakeDelay(rainfallTrend);
}

/* ----------------------------------------------------------------------- *
 * LINK SPOT E — Stage 3: Two-Tier Risk Modeling & Scoring (susceptibility map)
 * Owner: ML team (Scikit-Learn classifier output, fused with rule engine)
 * Real endpoint (suggested): GET {BASE_URL}/api/risk-zones?region=sikkim
 * Expected shape: array of { id, name, lat, lng, level, susceptibility }
 * This is what feeds the colored heatmap on Overview + Live Map.
 * ----------------------------------------------------------------------- */
export async function getRiskZones() {
  return fakeDelay(riskZones);
}

/* ----------------------------------------------------------------------- *
 * LINK SPOT F — Client Delivery: Citizen Reporting Form / PWA
 * Owner: Mobile/PWA team
 * Real endpoints (suggested):
 *   GET  {BASE_URL}/api/citizen-reports          (list, used by Citizen Reports page)
 *   POST {BASE_URL}/api/citizen-reports          (submit, used by the report form)
 * POST body shape: { location, note, lat, lng, photo (multipart) }
 * ----------------------------------------------------------------------- */
export async function getCitizenReports() {
  return fakeDelay(citizenReports);
}

export async function submitCitizenReport(payload) {
  // TODO(mobile/backend team): replace with a real multipart POST, e.g.
  // const form = new FormData();
  // Object.entries(payload).forEach(([k, v]) => form.append(k, v));
  // const res = await fetch(`${BASE_URL}/api/citizen-reports`, { method: "POST", body: form });
  // return res.json();
  console.log("[MOCK submitCitizenReport] payload:", payload);
  return fakeDelay({ ok: true, id: `CR-${Math.floor(Math.random() * 900)}` });
}

/* ----------------------------------------------------------------------- *
 * LINK SPOT G — Incidents log (post-event verification records)
 * Real endpoint (suggested): GET {BASE_URL}/api/incidents
 * ----------------------------------------------------------------------- */
export async function getIncidents() {
  return fakeDelay(incidents);
}

/* ----------------------------------------------------------------------- *
 * LINK SPOT H — Settings > Data Sources health panel
 * Real endpoint (suggested): GET {BASE_URL}/api/system/data-sources
 * ----------------------------------------------------------------------- */
export async function getDataSources() {
  return fakeDelay(dataSources);
}

/* ----------------------------------------------------------------------- *
 * LINK SPOT I — Scrolling warning ticker  (NEW IN DRAFT 2)
 * Stage 5: Notification & Alert Dispatch — the "public bulletin" text feed
 * Owner: Notifications team (or whoever owns the IMD bulletin scrape)
 * Real endpoint (suggested): GET {BASE_URL}/api/bulletins/ticker
 * Expected shape: array of { id, severity, text, issuedAt }
 *   severity: "High" | "Moderate" | "Low"
 *   text:     one sentence, plain language, no HTML
 *   issuedAt: display string, e.g. "issued 03 Sep, 08:30 IST"
 *
 * Rendered by src/components/AlertTicker.jsx, mounted once inside
 * src/layouts/DashboardLayout.jsx so it appears on every page.
 * Refresh cadence is set by TICKER_REFRESH_MS in DashboardLayout.jsx.
 * ----------------------------------------------------------------------- */
export async function getTickerBulletins() {
  // TODO(backend): replace with:
  // const res = await fetch(`${BASE_URL}/api/bulletins/ticker`);
  // return res.json();
  return fakeDelay(tickerBulletins);
}
