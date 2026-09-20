/**
 * ============================================================================
 *  API SERVICE LAYER — wired to the real backend
 * ============================================================================
 * Real backend: FastAPI + PostgreSQL/PostGIS. LINK SPOTS A-F and K call it
 * for real. G, H, I, J, L, N stay on mock data on purpose -- either out of
 * this round's 2-feature scope (incidents, data sources, ticker), require a
 * login system this project doesn't have yet (admin profile, notifications
 * -- matches this frontend's own documented design), or are already
 * client-side only by design (the incident PDF).
 *
 * Set VITE_API_BASE_URL in a .env file (see .env.example) once the backend
 * is deployed. Falls back to localhost for local dev against a locally
 * running backend.
 * ============================================================================
 */

import {
  incidents,
  dataSources,
  tickerBulletins,
  adminProfile,
  citizenReports as mockCitizenReports,
  notifications,
  emergencyContacts,
} from "../data/mockData";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// Server-Sent Events endpoint (see useAlertStream.js) -- exported here so
// this file stays the one place that knows the backend's base URL.
export const ALERT_STREAM_URL = `${BASE_URL}/alerts/stream`;

// ---------------------------------------------------------------------------
// Officer access key. The backend requires it (X-API-Key header) for every
// write action and for the endpoints that return personal data (citizen
// reports, authority contacts). It is typed in by the officer and kept only
// for this browser tab (sessionStorage) -- never baked into the built site,
// where anyone could read it.
// ---------------------------------------------------------------------------
const OFFICER_KEY_STORAGE = "resq_officer_key";

export function getOfficerKey() {
  try {
    return sessionStorage.getItem(OFFICER_KEY_STORAGE) || "";
  } catch {
    return "";
  }
}

export function setOfficerKey(key) {
  try {
    if (key) sessionStorage.setItem(OFFICER_KEY_STORAGE, key);
    else sessionStorage.removeItem(OFFICER_KEY_STORAGE);
  } catch {
    // storage blocked (private window etc.) -- the key just won't persist
  }
}

export class AuthRequiredError extends Error {
  constructor(status) {
    super(
      status === 429
        ? "Too many failed attempts -- wait a minute and try again."
        : "Officer access key required -- enter it with the lock icon in the top bar.",
    );
    this.name = "AuthRequiredError";
    this.status = status;
  }
}

function withOfficerKey(headers = {}) {
  const key = getOfficerKey();
  return key ? { ...headers, "X-API-Key": key } : headers;
}

// fetch() for endpoints that need the officer key. A 401/429 becomes an
// AuthRequiredError, so callers can tell "not signed in" from a real failure.
async function officerFetch(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers: withOfficerKey(options.headers) });
  if (res.status === 401 || res.status === 429) throw new AuthRequiredError(res.status);
  return res;
}

// Checks a typed-in key against the server (a cheap protected read) so a typo
// is caught at sign-in instead of failing every later action.
export async function verifyOfficerKey(key) {
  try {
    const res = await fetch(`${BASE_URL}/authority-contacts`, { headers: { "X-API-Key": key } });
    if (res.status === 401) return "invalid";
    if (res.status === 429) return "throttled";
    return res.ok ? "ok" : "error";
  } catch {
    return "error";
  }
}

// Whether the backend enforces the key at all (GET /health) -- the lock icon
// is only shown when it does.
export async function getOfficerAuthMode() {
  const health = await getJSON("/health");
  return health.officer_auth === "enabled" ? "enabled" : "disabled";
}

const fakeDelay = (data, ms = 200) =>
  new Promise((resolve) => setTimeout(() => resolve(data), ms));

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

// Several functions need the same endpoint (e.g. both /zones and /alerts are
// read by 3-4 different functions on the Overview page alone). With
// thousands of real zones loaded, /zones is a multi-second call -- firing it
// several times concurrently on one page load multiplies load on an
// already-slow free-tier backend for no reason. This coalesces near-
// simultaneous calls to the same path into a single network request.
const inFlight = new Map();

// /zones is 3,921 static rows (~1.1MB, ~7s from Render's free tier) and the
// model scores behind it don't change between page views, so its result is
// kept for 10 minutes -- Overview, the map, and search all reuse one fetch
// instead of each paying 7s. Alerts and reports can change during a live
// demo (a report submitted from a phone must show up), so they stay near-
// live at 3s.
// Matched by prefix, not exact equality -- every /zones call now carries a
// query string (?limit=...&state=...), so a plain `CACHE_TTL_MS[path]`
// lookup never matched and every zones fetch silently fell back to the 3s
// default below instead of the intended 10 minutes, once limit/state were
// added to every call site. Re-fetching thousands of rows on effectively
// every page view was the real cause of the dashboard "still" feeling slow
// after the backend performance fix -- not a regression in the backend
// itself, confirmed by re-timing GET /zones directly.
const CACHE_TTL_MS_PREFIXES = [["/zones", 10 * 60 * 1000]];
function cacheTtlFor(path) {
  const hit = CACHE_TTL_MS_PREFIXES.find(([prefix]) => path.startsWith(prefix));
  return hit ? hit[1] : 3000;
}

// GET /zones is a capped, paged list (DEFAULT_ZONE_LIMIT=2000, max 5000 in
// app/routers/zones.py) -- an unbounded response once timed out the API
// completely at Assam's 66,677 zones. Nothing here downloads "all the zones"
// any more: the map asks /zones/map for just what's in view, the cards ask
// /zones/stats for counts, and search/nearest-safer are answered by the
// backend. What's left is "the highest-risk N zones" for the few features
// that only need a handful of candidates.
function topZonesPath(state, limit = 15) {
  const params = new URLSearchParams({ limit });
  if (state) params.set("state", state);
  return `/zones?${params.toString()}`;
}

function alertsPath(state) {
  return state ? `/alerts?state=${encodeURIComponent(state)}` : "/alerts";
}

async function getJSON(path, { auth = false } = {}) {
  if (inFlight.has(path)) return inFlight.get(path);
  const promise = fetch(`${BASE_URL}${path}`, auth ? { headers: withOfficerKey() } : undefined).then((res) => {
    if (auth && (res.status === 401 || res.status === 429)) throw new AuthRequiredError(res.status);
    if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
    return res.json();
  });
  promise.then(
    () => setTimeout(() => inFlight.delete(path), cacheTtlFor(path)),
    // Never hold on to a failure: a Retry click must hit the network again,
    // not get handed back the same rejected promise.
    () => inFlight.delete(path),
  );
  inFlight.set(path, promise);
  return promise;
}

// Real risk_tier values are lowercase ("low"/"moderate"/"high") in the
// database; every page/component here expects the capitalised form
// ("Low"/"Moderate"/"High"), matching the mock data's original casing.
//
// A null tier used to fall back to "Moderate" -- silently indistinguishable
// from a zone the model actually rated moderate risk (a real, previously
// flagged honesty gap: an officer could deprioritize an actually-high-risk
// but not-yet-modeled zone because it looked like an ordinary moderate one).
// "Unscored" is a distinct value every consumer (RiskMap, RiskLegend,
// ZoneDetail, HighwayCorridors) renders differently from a real tier.
function capitalizeTier(tier) {
  if (!tier) return "Unscored";
  return tier.charAt(0).toUpperCase() + tier.slice(1);
}

function timeAgo(isoString) {
  const diffMs = Date.now() - new Date(isoString).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs} hr${hrs > 1 ? "s" : ""} ago`;
  const days = Math.round(hrs / 24);
  return `${days} day${days > 1 ? "s" : ""} ago`;
}

// One place that turns a backend alert into what the UI shows, so the Alerts
// page and the zone page can't drift apart.
function shapeAlert(a) {
  return {
    id: a.id,
    zoneId: a.zone_id,
    title: a.threshold_crossed,
    location: a.zone_name || "Unknown zone",
    severity: capitalizeTier(a.risk_tier),
    timeAgo: timeAgo(a.triggered_at),
    status: a.status,
    // "system" = closed automatically because the rainfall cleared;
    // "officer" = closed by a person; null = resolved before this was recorded.
    resolvedBy: a.resolved_by || null,
    resolvedAgo: a.resolved_at ? timeAgo(a.resolved_at) : null,
  };
}

// Active alerts first (that's what an officer needs), newest first within each group.
function byActiveThenNewest(a, b) {
  return (
    (a.status === "active" ? 0 : 1) - (b.status === "active" ? 0 : 1) ||
    new Date(b.triggered_at) - new Date(a.triggered_at)
  );
}

// AlertOut now carries zone_name/risk_tier directly (the backend joins them
// server-side), so this no longer needs a separate full /zones fetch just to
// label each alert -- that used to mean pulling all 3921 zones for a handful
// of alerts.
async function fetchAndShapeAlerts(state) {
  const alerts = await getJSON(alertsPath(state));
  return alerts.slice().sort(byActiveThenNewest).map(shapeAlert);
}

// Not every zone has had live rainfall fetched yet (fetching is an explicit,
// real Open-Meteo call per zone -- not something to do for all 3921 at
// once). Picking a fixed zone (e.g. always zones[0]) risks landing on one
// with no data purely by chance. This tries the highest-susceptibility
// zones first (a real, defensible priority -- watch the most dangerous
// corridors first) and returns the first one that actually has readings.
async function findZoneWithRainfall(zones, tryCount = 15) {
  const candidates = zones
    .slice()
    .sort((a, b) => (b.susceptibility_score ?? 0) - (a.susceptibility_score ?? 0))
    .slice(0, tryCount);
  // Asked in parallel, then the highest-priority zone that has readings wins.
  // One at a time, a state with no stored rainfall at all (most newly added
  // states) cost 15 sequential requests -- the whole Overview sat on
  // "Loading" for ~18 s when switching to Assam.
  const results = await Promise.allSettled(candidates.map((zone) => getJSON(`/rainfall/${zone.id}`)));
  for (let i = 0; i < candidates.length; i++) {
    const r = results[i];
    if (r.status === "fulfilled" && r.value.length > 0) return { zone: candidates[i], readings: r.value };
  }
  return null;
}

/* ----------------------------------------------------------------------- *
 * LINK SPOT A — Overview summary cards.
 * No single backend endpoint returns this -- assembled client-side from
 * /zones and /alerts, plus a live /health check for system status.
 * Villages-affected and a 24h rainfall total aren't tracked concepts in the
 * current schema, so those two are honestly approximated (zones with an
 * active alert; latest reading from the highest-risk zone with data)
 * rather than invented.
 * ----------------------------------------------------------------------- */
export async function getSummaryStats(state) {
  // Counts come from /zones/stats (computed over every zone in the database)
  // and alerts are filtered by state server-side. Both used to be derived by
  // downloading every zone of the state, which capped out at a few thousand
  // and stops working entirely at tens of thousands.
  const [stats, alerts, topZones] = await Promise.all([
    getZoneStats(state),
    getJSON(alertsPath(state)),
    getJSON(topZonesPath(state)),
  ]);
  const activeAlerts = alerts.filter((a) => a.status === "active");
  const affectedZoneIds = new Set(activeAlerts.map((a) => a.zone_id));

  let rainfall24hLabel = "No data yet";
  let rainfallZoneName = "No zone yet";
  const found = await findZoneWithRainfall(topZones);
  if (found) {
    // GET /rainfall/{id} returns newest-first, but that ordering isn't
    // guaranteed by contract -- picking by an explicit timestamp comparison
    // (rather than assuming index 0 or the last index) avoided a real bug
    // here where this previously read readings[length-1], i.e. the OLDEST
    // fetched day, and labeled it "Rainfall (24h)".
    const latest = found.readings.reduce((a, b) => (new Date(a.timestamp) > new Date(b.timestamp) ? a : b));
    rainfall24hLabel = `${latest.intensity_mm.toFixed(0)} mm`;
    rainfallZoneName = found.zone.name;
  }

  let systemHealthy = false;
  try {
    const health = await getJSON("/health");
    systemHealthy = health.status === "ok";
  } catch {
    systemHealthy = false;
  }

  return {
    highRiskZones: { value: stats.high, total: stats.total, trend: "flat" },
    activeAlerts: { value: activeAlerts.length, deltaLabel: `${affectedZoneIds.size} zone(s) affected`, trend: activeAlerts.length > 0 ? "up" : "flat" },
    affectedVillages: { value: affectedZoneIds.size, deltaLabel: "Zones with an active alert", trend: "flat" },
    rainfall24h: { value: rainfall24hLabel, deltaLabel: rainfallZoneName, trend: "flat" },
    systemHealth: { value: systemHealthy ? "100%" : "Down", deltaLabel: systemHealthy ? "Backend responding" : "Backend unreachable", trend: systemHealthy ? "good" : "down" },
  };
}

/* LINK SPOT B / C — alerts. `state`, when given, scopes this to the
 * currently selected NER state (Overview's AlertsPanel) -- filtered by the
 * backend (GET /alerts?state=), since an alert belongs to a state through
 * its zone. getRecentAlerts (the standalone Alerts page) stays
 * intentionally global across all regions, unaffected. */
export async function getActiveAlerts(state) {
  const shaped = await fetchAndShapeAlerts(state);
  return shaped.filter((a) => a.status === "active");
}

export async function getRecentAlerts() {
  return fetchAndShapeAlerts();
}

/* ----------------------------------------------------------------------- *
 * LINK SPOT D — Rainfall trend chart. No region-wide trend endpoint exists
 * (rainfall is stored per zone), so this shows the first zone's last 7
 * readings -- a reasonable stand-in until there's more than one seeded zone.
 * ----------------------------------------------------------------------- */
function isToday(isoTimestamp) {
  const d = new Date(isoTimestamp);
  const now = new Date();
  return d.toDateString() === now.toDateString();
}

// Shared by getRainfallTrend and getRainfallForZone -- both used to
// independently sort+map the exact same reading shape (a real duplicate,
// not just similar-looking code): GET /rainfall/{id} returns newest-first,
// POST .../fetch returns whatever order Open-Meteo's response was in, so
// this sorts explicitly rather than trusting either implicit order.
function shapeRainfallReadings(readings, { limit } = {}) {
  const ascending = readings.slice().sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
  const windowed = limit ? ascending.slice(-limit) : ascending;
  return windowed.map((r) => ({
    day: new Date(r.timestamp).toLocaleDateString(undefined, { month: "short", day: "numeric" }),
    mm: Math.round(r.intensity_mm),
    // See app/schemas.py RainfallReadingOut.is_forecast -- open_meteo's
    // forecast_days window is stored the same as real past_days readings,
    // so the chart needs this to avoid showing an unconfirmed forecast day
    // as if it were observed rainfall.
    isForecast: Boolean(r.is_forecast),
  }));
}

// The real, config-driven per-zone threshold (app/services/alert_engine.py,
// scaled by this zone's own risk_tier) -- replaces a hardcoded, fake flat
// 100mm constant the chart used to plot real rainfall against with no
// relationship to what actually fires an alert. null (not a guessed
// number) when this zone's state has no configured threshold yet (e.g.
// Mizoram today) -- RainfallChart.jsx skips drawing the reference line
// entirely in that case rather than showing a fabricated one.
export async function getRainfallThreshold(zoneId) {
  const res = await fetch(`${BASE_URL}/rainfall/${zoneId}/threshold`);
  if (!res.ok) throw new Error(`load threshold failed: ${res.status}`);
  const t = await res.json();
  return t ? { mm: t.threshold_mm_per_day, source: t.source, verified: t.verified_against_primary_text } : null;
}

export async function getRainfallTrend(state) {
  const zones = await getJSON(topZonesPath(state));
  if (zones.length === 0) return { readings: [], threshold: null };
  const found = await findZoneWithRainfall(zones);
  if (!found) return { readings: [], threshold: null };

  let readings = found.readings;
  const newest = readings.reduce((a, b) => (new Date(a.timestamp) > new Date(b.timestamp) ? a : b));

  // The batch script that originally seeded rainfall only ran once -- without
  // this, the chart would keep showing whatever week that one run happened to
  // fetch, forever. Re-fetching live from Open-Meteo when the newest stored
  // reading isn't from today keeps this genuinely current, not a frozen
  // snapshot; at most once per zone per day, since every other page load that
  // same day already finds a "today" reading and skips straight past this.
  if (!isToday(newest.timestamp)) {
    try {
      const res = await officerFetch(`/rainfall/${found.zone.id}/fetch`, { method: "POST" });
      if (res.ok) {
        const fresh = await res.json();
        if (fresh.length > 0) readings = fresh;
      }
    } catch {
      // Open-Meteo/network hiccup -- fall back to the (possibly stale)
      // readings already fetched above rather than fail the whole card.
    }
  }

  let threshold = null;
  try {
    threshold = await getRainfallThreshold(found.zone.id);
  } catch {
    // Threshold lookup failing shouldn't take down the whole rainfall
    // card -- the chart just skips the reference line (same as "no
    // threshold configured"), same fallback posture as the fetch above.
  }

  return { readings: shapeRainfallReadings(readings, { limit: 7 }), threshold };
}

/* ----------------------------------------------------------------------- *
 * LINK SPOT E — Risk zones for the map. The map never holds every zone: it
 * asks GET /zones/map for what's in the current viewport, and the backend
 * answers with individual zones when few are in view or grid clusters
 * (count + per-tier counts) when many are. centroid_lat/centroid_lng are
 * computed server-side (see app/models.py Zone.centroid_lat/lng) from the
 * stored polygon, since the map needs one point per zone, not the full shape.
 * ----------------------------------------------------------------------- */

// Counts over EVERY zone, plus the extent to fit the map to.
export async function getZoneStats(state) {
  const path = state ? `/zones/stats?state=${encodeURIComponent(state)}` : "/zones/stats";
  return getJSON(path);
}

function shapeZone(z) {
  return {
    id: z.id,
    name: z.name,
    state: z.state,
    lat: z.centroid_lat,
    lng: z.centroid_lng,
    level: capitalizeTier(z.risk_tier),
    // Preserved as null, not coerced to 0 -- an unscored zone (no ML result
    // yet) is not the same claim as "confirmed 0% risk," and RiskMap.jsx
    // renders the two states differently (a real 0% zone gets the smallest
    // real marker; an unscored zone gets an explicit "not yet scored"
    // marker/tooltip instead of silently looking like the safest zone on
    // the map).
    susceptibility: z.susceptibility_score,
  };
}

// Rounded to 4 decimals (~11 m) so two nearly identical viewports share one
// cached response instead of each panning pixel being a new request.
const r4 = (n) => Math.round(n * 1e4) / 1e4;

export async function getMapView(state, { minLat, minLng, maxLat, maxLng }) {
  const params = new URLSearchParams({
    min_lat: r4(minLat),
    min_lng: r4(minLng),
    max_lat: r4(maxLat),
    max_lng: r4(maxLng),
  });
  if (state) params.set("state", state);
  const view = await getJSON(`/zones/map?${params.toString()}`);
  return {
    mode: view.mode,
    total: view.total,
    zones: view.zones.map(shapeZone),
    clusters: view.clusters,
  };
}

/* ----------------------------------------------------------------------- *
 * Nearest lower-risk zone -- an officer/citizen on Zone Detail needs "which
 * way is safer," not just a susceptibility number. Real data only: the
 * backend (GET /zones/{id}/nearest-safer) searches this zone's own state (a
 * "safe" zone in a different state isn't reachable-by-road information this
 * system has), among zones that are actually scored -- unscored zones are
 * never offered as the safer option, so this never recommends fleeing toward
 * an unassessed area. Distance is great-circle, not a road route: this hands
 * off to Google Maps for real turn-by-turn directions (see ZoneDetail.jsx)
 * instead of pretending to have them. `nearest` is null when nothing is safer.
 * ----------------------------------------------------------------------- */
export async function getNearestSafeZone(zoneId) {
  const res = await fetch(`${BASE_URL}/zones/${zoneId}/nearest-safer`);
  if (!res.ok) throw new Error(`load nearest safer zone failed: ${res.status}`);
  const nearest = await res.json();
  // Wrapped so "still loading" (the hook's null) and "nothing safer nearby"
  // ({ nearest: null }) are different values -- as a bare null they were the
  // same, and the page showed "no lower-risk zone nearby" for the whole load.
  return { nearest: nearest ? { ...shapeZone(nearest), distanceKm: nearest.distance_km } : null };
}

/* ----------------------------------------------------------------------- *
 * LINK SPOT N — Highway corridors. Real: GET /corridors groups the same
 * 3,921 real zones by the highway/road code already embedded in each zone's
 * name (e.g. "NH310A" from "NH310A (1224920841_00_000)") -- no new data
 * source, just a different aggregation of what /zones already serves.
 * ----------------------------------------------------------------------- */
export async function getCorridors(state) {
  const corridors = await getJSON(state ? `/corridors?state=${encodeURIComponent(state)}` : "/corridors");
  return corridors.map((c) => ({
    code: c.code,
    zoneCount: c.zone_count,
    activeAlertCount: c.active_alert_count,
    worstTier: capitalizeTier(c.worst_risk_tier),
    worstZoneName: c.worst_zone_name,
    worstScore: c.worst_susceptibility_score,
  }));
}

/* ----------------------------------------------------------------------- *
 * LINK SPOT F — Citizen reports.
 * ----------------------------------------------------------------------- */
function verifiedStatusLabel(status) {
  return { unverified: "Pending verification", verified: "Verified", rejected: "Rejected" }[status] || status;
}

function shapeReport(r) {
  const hasCoords = r.geo_lat != null && r.geo_lng != null;
  return {
    id: r.id,
    reporter: r.reporter_name || "Anonymous",
    // CitizenReportModal reads reporterName/reporterPhone/area -- these were
    // previously missing here (a leftover mismatch from mockData.js's mock
    // shape, which had different field names), so every real report showed
    // blank Area/Submitted By/Contact rows despite the data existing in
    // CitizenReport.reporter_name/reporter_phone/place_name. reporterType
    // and weatherAtReport have no real backend field (CitizenReportOut has
    // no such columns) -- left undefined/"Not recorded" rather than
    // inventing a value, matching this project's honesty rule.
    reporterName: r.reporter_name || "Anonymous",
    reporterPhone: r.reporter_phone || "Not recorded",
    area: r.place_name || "Not recorded",
    weatherAtReport: "Not recorded",
    location: r.place_name || (hasCoords ? `${r.geo_lat.toFixed(5)}, ${r.geo_lng.toFixed(5)}` : "Unknown location"),
    lat: hasCoords ? r.geo_lat.toFixed(5) : "",
    lng: hasCoords ? r.geo_lng.toFixed(5) : "",
    landmark: r.place_name || "",
    note: r.description,
    triageSummary: r.triage_summary || null,
    descriptionTranslated: r.description_translated || null,
    status: verifiedStatusLabel(r.verified_status),
    photoPlaceholder: !r.photo_url,
    photoUrl: r.photo_url,
    submittedAt: new Date(r.submitted_at).toLocaleString(undefined, { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }),
  };
}

export async function getCitizenReports() {
  const reports = await getJSON("/reports", { auth: true });
  return reports.map(shapeReport);
}

// The dashboard's own quick-add form only collects a location + note (no
// hazard type/severity/GPS -- that's the full citizen-facing form's job,
// built separately). Reasonable defaults fill in what POST /reports needs.
export async function submitCitizenReport(payload) {
  const body = {
    reportType: "other",
    severity: "moderate",
    placeName: payload.location,
    description: payload.note,
    capturedAt: new Date().toISOString(),
  };
  const form = new FormData();
  form.append("data", JSON.stringify(body));
  const res = await fetch(`${BASE_URL}/reports`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`submit report failed: ${res.status}`);
  return res.json();
}

/* ----------------------------------------------------------------------- *
 * Zone Detail — drill-down from clicking a marker on the risk map. Reuses
 * the same real endpoints already used elsewhere (GET /zones/{id},
 * GET /rainfall/{id}, GET /alerts filtered client-side by zone_id since
 * there's no ?zone_id= filter on /alerts yet) rather than adding new
 * backend surface for a page that's just a different view of existing data.
 * ----------------------------------------------------------------------- */
export async function getZoneById(zoneId) {
  const res = await fetch(`${BASE_URL}/zones/${zoneId}`);
  if (!res.ok) throw new Error(`load zone failed: ${res.status}`);
  const z = await res.json();
  return {
    id: z.id, name: z.name, state: z.state,
    lat: z.centroid_lat, lng: z.centroid_lng,
    level: capitalizeTier(z.risk_tier),
    susceptibility: z.susceptibility_score,
    modelVersion: z.model_version,
    lastUpdated: z.last_updated,
  };
}

export async function getRainfallForZone(zoneId) {
  const readings = await getJSON(`/rainfall/${zoneId}`);
  let threshold = null;
  try {
    threshold = await getRainfallThreshold(zoneId);
  } catch {
    // Same fallback posture as getRainfallTrend -- a threshold-lookup
    // failure shouldn't take down the whole rainfall history panel.
  }
  return { readings: shapeRainfallReadings(readings), threshold };
}

export async function getAlertsForZone(zoneId) {
  const alerts = await getJSON("/alerts");
  return alerts
    .filter((a) => a.zone_id === zoneId)
    .slice()
    .sort(byActiveThenNewest)
    .map(shapeAlert);
}

/* ----------------------------------------------------------------------- *
 * Authority Contacts — the real call-list app.services.sms_alerts.
 * escalate_critical_alert reads on a "critical" broadcast. Previously only
 * addable via a direct DB insert; this is what makes that feature usable by
 * an officer, not just a developer. Not cached via getJSON since this list
 * is short and changes rarely but must always be fresh right after an add
 * or delete.
 * ----------------------------------------------------------------------- */
export async function getAuthorityContacts() {
  const res = await officerFetch("/authority-contacts");
  if (!res.ok) throw new Error(`load authority contacts failed: ${res.status}`);
  return res.json();
}

export async function addAuthorityContact({ name, role, phoneNumber }) {
  const res = await officerFetch("/authority-contacts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, role: role || null, phone_number: phoneNumber }),
  });
  if (!res.ok) throw new Error(`add authority contact failed: ${res.status}`);
  return res.json();
}

export async function deleteAuthorityContact(contactId) {
  const res = await officerFetch(`/authority-contacts/${contactId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`delete authority contact failed: ${res.status}`);
}

/* ----------------------------------------------------------------------- *
 * Out of scope for this round -- no backend endpoint exists (incidents,
 * data-source health, the warning ticker). Left on mock data on purpose,
 * not connected.
 * ----------------------------------------------------------------------- */
export async function getIncidents() {
  return fakeDelay(incidents);
}

export async function getDataSources() {
  return fakeDelay(dataSources);
}

/* ----------------------------------------------------------------------- *
 * LINK SPOT P — Emergency contacts. Real public helpline numbers, but a
 * static directory (not synced live against any government system) -- same
 * honesty as Data & Observations above, just phone numbers instead of feed
 * status. This genuinely cannot fail (no network call), so it skips
 * useAsyncData the same way getDataSources does.
 * ----------------------------------------------------------------------- */
export async function getEmergencyContacts() {
  return fakeDelay(emergencyContacts);
}

export async function getTickerBulletins() {
  return fakeDelay(tickerBulletins);
}

/* ----------------------------------------------------------------------- *
 * LINK SPOT J — Admin profile. Genuinely depends on a login system this
 * project doesn't have yet (matches this frontend's own documented design
 * -- "Owner: Backend team, once authentication is added"). Stays mocked
 * honestly rather than wired to a fake single-user backend record.
 * ----------------------------------------------------------------------- */
export async function getAdminProfile() {
  return fakeDelay(adminProfile, 150);
}

export async function updateAdminProfile(profile) {
  return fakeDelay({ ok: true, profile }, 200);
}

/* ----------------------------------------------------------------------- *
 * LINK SPOT K — Verify a citizen report. Real: flips verified_status to
 * "verified" via the backend's new POST /reports/{id}/verify.
 * ----------------------------------------------------------------------- */
export async function verifyCitizenReport(reportId) {
  const res = await officerFetch(`/reports/${reportId}/verify`, { method: "POST" });
  if (!res.ok) throw new Error(`verify report failed: ${res.status}`);
  return res.json();
}

/* ----------------------------------------------------------------------- *
 * LINK SPOT O — Alert broadcast. Real: POST /alerts/{id}/broadcast writes a
 * real row (headline, message, channels, timestamp). status always comes
 * back "simulated" -- no SMS/CAP/siren gateway is wired up yet, same
 * honesty as delivery_method="log_only" on the alert itself.
 * ----------------------------------------------------------------------- */
/* ----------------------------------------------------------------------- *
 * AI-drafted bulletin for the Broadcast composer -- POST /alerts/{id}/
 * generate-bulletin (Gemini, see app/services/bulletin.py). The officer
 * reviews and can edit every word before sending; this only saves them
 * writing a headline/message from scratch.
 * ----------------------------------------------------------------------- */
export async function generateBulletin(alertId, severity) {
  const res = await officerFetch(`/alerts/${alertId}/generate-bulletin`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ severity }),
  });
  if (!res.ok) throw new Error(`generate bulletin failed: ${res.status}`);
  return res.json();
}

export async function broadcastAlert(alertId, { headline, severity, message, channels }) {
  const res = await officerFetch(`/alerts/${alertId}/broadcast`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ headline, severity, message, channels }),
  });
  if (!res.ok) throw new Error(`broadcast failed: ${res.status}`);
  return res.json();
}

/* ----------------------------------------------------------------------- *
 * LINK SPOT L — Incident report download. Already client-side only by
 * design (jsPDF, no backend needed) -- incidents themselves are mock (out
 * of scope), so the citizen reports bundled into the PDF stay mock too for
 * internal consistency (a real citizen report has no "area" field to match
 * a mock incident's area against).
 * ----------------------------------------------------------------------- */
export async function getIncidentReportBundle(incidentId) {
  const incident = incidents.find((i) => i.id === incidentId);
  const related = mockCitizenReports.filter((r) => r.area === incident?.area);
  return fakeDelay({ incident, citizenReports: related }, 150);
}

/* ----------------------------------------------------------------------- *
 * LINK SPOT M — Global search. Real: searches actual zones, alerts, and
 * citizen reports. Incidents stay mock (out of scope), included anyway so
 * the search doesn't silently drop a whole category the UI advertises --
 * each result routes to a page that's itself honest about being mock.
 * ----------------------------------------------------------------------- */
export async function searchAll(query) {
  const q = query.trim().toLowerCase();
  if (!q) return [];

  // Zone names are searched by the backend (min 2 characters there) rather
  // than downloading every zone and filtering in the browser.
  const [zones, alerts, reports] = await Promise.all([
    q.length >= 2 ? getJSON(`/zones?q=${encodeURIComponent(q)}&limit=20`) : Promise.resolve([]),
    fetchAndShapeAlerts(),
    // Citizen reports need the officer key; without it, search just skips them.
    getCitizenReports().catch(() => []),
  ]);

  const results = [];

  for (const z of zones) {
    if (z.name.toLowerCase().includes(q)) {
      results.push({ id: z.id, type: "Zone", title: z.name, subtitle: `${capitalizeTier(z.risk_tier)} risk`, to: `/zones/${z.id}` });
    }
  }
  for (const a of alerts) {
    if (a.title.toLowerCase().includes(q) || a.location.toLowerCase().includes(q)) {
      results.push({ id: a.id, type: "Alert", title: a.location, subtitle: a.title, to: "/alerts" });
    }
  }
  for (const r of reports) {
    if (r.note.toLowerCase().includes(q) || r.location.toLowerCase().includes(q)) {
      results.push({ id: r.id, type: "Citizen report", title: r.location, subtitle: r.note, to: "/citizen-reports" });
    }
  }
  for (const inc of incidents) {
    if (inc.location.toLowerCase().includes(q) || inc.area?.toLowerCase().includes(q)) {
      results.push({ id: inc.id, type: "Incident", title: inc.location, subtitle: inc.status, to: "/incidents" });
    }
  }

  return results.slice(0, 12);
}

/* ----------------------------------------------------------------------- *
 * LINK SPOT N — Notifications. Genuinely depends on login ("unread" means
 * unread BY A PARTICULAR OFFICER) -- matches this frontend's own documented
 * design. Stays mocked honestly rather than faked as personal.
 * ----------------------------------------------------------------------- */
export async function getNotifications() {
  return fakeDelay(notifications, 200);
}

export async function markNotificationsRead() {
  return fakeDelay({ ok: true }, 150);
}
