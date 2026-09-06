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
} from "../data/mockData";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

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

async function getJSON(path) {
  if (inFlight.has(path)) return inFlight.get(path);
  const promise = fetch(`${BASE_URL}${path}`)
    .then((res) => {
      if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
      return res.json();
    })
    .finally(() => {
      setTimeout(() => inFlight.delete(path), 3000);
    });
  inFlight.set(path, promise);
  return promise;
}

// Real risk_tier values are lowercase ("low"/"moderate"/"high") in the
// database; every page/component here expects the capitalised form
// ("Low"/"Moderate"/"High"), matching the mock data's original casing.
function capitalizeTier(tier) {
  if (!tier) return "Moderate";
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

// The real alerts table has no "title"/"location"/"severity" fields -- those
// come from the zone it's linked to, plus the threshold_crossed text the
// backend already writes a human-readable description into.
async function fetchAndShapeAlerts() {
  const [alerts, zones] = await Promise.all([getJSON("/alerts"), getJSON("/zones")]);
  const zoneById = Object.fromEntries(zones.map((z) => [z.id, z]));
  return alerts
    .slice()
    .sort((a, b) => new Date(b.triggered_at) - new Date(a.triggered_at))
    .map((a) => {
      const zone = zoneById[a.zone_id];
      return {
        id: a.id,
        title: a.threshold_crossed,
        location: zone?.name || "Unknown zone",
        severity: capitalizeTier(zone?.risk_tier),
        timeAgo: timeAgo(a.triggered_at),
        status: a.status,
      };
    });
}

/* ----------------------------------------------------------------------- *
 * LINK SPOT A — Overview summary cards.
 * No single backend endpoint returns this -- assembled client-side from
 * /zones and /alerts, plus a live /health check for system status.
 * Villages-affected and a 24h rainfall total aren't tracked concepts in the
 * current schema, so those two are honestly approximated (zones with an
 * active alert; latest reading from the first zone) rather than invented.
 * ----------------------------------------------------------------------- */
export async function getSummaryStats() {
  const [zones, alerts] = await Promise.all([getJSON("/zones"), getJSON("/alerts")]);
  const highRisk = zones.filter((z) => z.risk_tier === "high").length;
  const activeAlerts = alerts.filter((a) => a.status === "active");
  const affectedZoneIds = new Set(activeAlerts.map((a) => a.zone_id));

  let rainfall24hLabel = "No data yet";
  if (zones.length > 0) {
    try {
      const readings = await getJSON(`/rainfall/${zones[0].id}`);
      if (readings.length > 0) {
        const latest = readings[readings.length - 1];
        rainfall24hLabel = `${latest.intensity_mm.toFixed(0)} mm`;
      }
    } catch {
      // No rainfall fetched for this zone yet -- keep the "No data yet" label.
    }
  }

  let systemHealthy = false;
  try {
    const health = await getJSON("/health");
    systemHealthy = health.status === "ok";
  } catch {
    systemHealthy = false;
  }

  return {
    highRiskZones: { value: highRisk, deltaLabel: `${zones.length} zone(s) total`, trend: "flat" },
    activeAlerts: { value: activeAlerts.length, deltaLabel: `${affectedZoneIds.size} zone(s) affected`, trend: activeAlerts.length > 0 ? "up" : "flat" },
    affectedVillages: { value: affectedZoneIds.size, deltaLabel: "Zones with an active alert", trend: "flat" },
    rainfall24h: { value: rainfall24hLabel, deltaLabel: zones.length > 0 ? zones[0].name : "No zone yet", trend: "flat" },
    systemHealth: { value: systemHealthy ? "100%" : "Down", deltaLabel: systemHealthy ? "Backend responding" : "Backend unreachable", trend: systemHealthy ? "good" : "down" },
  };
}

/* LINK SPOT B / C — alerts */
export async function getActiveAlerts() {
  const shaped = await fetchAndShapeAlerts();
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
export async function getRainfallTrend() {
  const zones = await getJSON("/zones");
  if (zones.length === 0) return [];
  const readings = await getJSON(`/rainfall/${zones[0].id}`);
  return readings.slice(-7).map((r) => ({
    day: new Date(r.timestamp).toLocaleDateString(undefined, { month: "short", day: "numeric" }),
    mm: Math.round(r.intensity_mm),
  }));
}

/* ----------------------------------------------------------------------- *
 * LINK SPOT E — Risk zones for the map. centroid_lat/centroid_lng are
 * computed server-side (see app/models.py Zone.centroid_lat/lng) from the
 * stored polygon, since the map needs one point per zone, not the full shape.
 * ----------------------------------------------------------------------- */
export async function getRiskZones() {
  const zones = await getJSON("/zones");
  return zones.map((z) => ({
    id: z.id,
    name: z.name,
    lat: z.centroid_lat,
    lng: z.centroid_lng,
    level: capitalizeTier(z.risk_tier),
    susceptibility: z.susceptibility_score ?? 0,
  }));
}

/* ----------------------------------------------------------------------- *
 * LINK SPOT F — Citizen reports.
 * ----------------------------------------------------------------------- */
function verifiedStatusLabel(status) {
  return { unverified: "Pending verification", verified: "Verified", rejected: "Rejected" }[status] || status;
}

function shapeReport(r) {
  return {
    id: r.id,
    reporter: r.reporter_name || "Anonymous",
    location: r.place_name || (r.geo_lat != null ? "GPS location" : "Unknown location"),
    note: r.description,
    status: verifiedStatusLabel(r.verified_status),
    photoPlaceholder: !r.photo_url,
    photoUrl: r.photo_url,
    submittedAt: new Date(r.submitted_at).toLocaleString(undefined, { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }),
  };
}

export async function getCitizenReports() {
  const reports = await getJSON("/reports");
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
  const res = await fetch(`${BASE_URL}/reports/${reportId}/verify`, { method: "POST" });
  if (!res.ok) throw new Error(`verify report failed: ${res.status}`);
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

  const [zones, alerts, reports] = await Promise.all([
    getJSON("/zones"),
    fetchAndShapeAlerts(),
    getCitizenReports(),
  ]);

  const results = [];

  for (const z of zones) {
    if (z.name.toLowerCase().includes(q)) {
      results.push({ id: z.id, type: "Zone", title: z.name, subtitle: `${capitalizeTier(z.risk_tier)} risk`, to: "/" });
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
