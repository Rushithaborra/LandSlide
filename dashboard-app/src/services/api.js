/**
 * ============================================================================
 *  API SERVICE LAYER — wired to the real backend
 * ============================================================================
 * Real backend: FastAPI + PostgreSQL/PostGIS. See ../../docs (in the main
 * repo) for the full endpoint contract. Two of the original LINK SPOTs
 * (G: incidents, H: data sources) plus the ticker (I) have no backend
 * equivalent -- they're out of this round's 2-feature scope (susceptibility
 * model + GIS heatmap, real-time alerts + citizen reporting) and stay on
 * mock data on purpose, not as an oversight.
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
} from "../data/mockData";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const fakeDelay = (data, ms = 200) =>
  new Promise((resolve) => setTimeout(() => resolve(data), ms));

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

async function getJSON(path) {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  return res.json();
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

// The real alerts table has no "title"/"location"/"severity" fields --
// those come from the zone it's linked to, plus the threshold_crossed
// text the backend already writes a human-readable description into.
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
 * Overview summary cards.
 * No single backend endpoint returns this -- it's assembled client-side
 * from /zones and /alerts, plus a live /health check for system status.
 * Villages-affected and a 24h rainfall total aren't tracked concepts in
 * the current schema, so those two are honestly approximated (zones with
 * an active alert; latest reading from the first zone) rather than
 * invented outright.
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

export async function getActiveAlerts() {
  const shaped = await fetchAndShapeAlerts();
  return shaped.filter((a) => a.status === "active");
}

export async function getRecentAlerts() {
  return fetchAndShapeAlerts();
}

/* ----------------------------------------------------------------------- *
 * Rainfall trend chart. There's no region-wide trend endpoint (rainfall is
 * stored per zone), so this shows the first zone's last 7 readings -- a
 * reasonable stand-in until there's more than one seeded zone.
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
 * Risk zones for the map. centroid_lat/centroid_lng are computed
 * server-side (see app/models.py Zone.centroid_lat/lng) from the stored
 * polygon, since the map needs one point per zone, not the full shape.
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
 * Citizen reports.
 * ----------------------------------------------------------------------- */
function verifiedStatusLabel(status) {
  return { unverified: "Pending verification", verified: "Verified", rejected: "Rejected" }[status] || status;
}

export async function getCitizenReports() {
  const reports = await getJSON("/reports");
  return reports.map((r) => ({
    id: r.id,
    reporter: r.reporter_name || "Anonymous",
    location: r.place_name || (r.geo_lat != null ? "GPS location" : "Unknown location"),
    note: r.description,
    status: verifiedStatusLabel(r.verified_status),
    photoPlaceholder: !r.photo_url,
    photoUrl: r.photo_url,
    submittedAt: new Date(r.submitted_at).toLocaleString(undefined, { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }),
  }));
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
 * Out of scope for this round -- no backend endpoint exists (see the file
 * header). Left on mock data on purpose, not connected.
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
