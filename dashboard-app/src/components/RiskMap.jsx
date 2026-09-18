import L from "leaflet";
import { MapContainer, TileLayer, Marker, Tooltip } from "react-leaflet";
import MarkerClusterGroup from "react-leaflet-cluster";
import { useNavigate } from "react-router-dom";
import "leaflet/dist/leaflet.css";
import "react-leaflet-cluster/dist/assets/MarkerCluster.css";
import "react-leaflet-cluster/dist/assets/MarkerCluster.Default.css";
import { useTheme } from "../context/ThemeContext";

/**
 * RiskMap
 * -------
 * LINK SPOT E (see src/services/api.js and LINKING_GUIDE.md):
 * `zones` should come from the Stage 3 Risk Engine Fusion output
 * (GET /api/risk-zones). Right now the parent page passes mock zones.
 *
 * Uses Leaflet + OpenStreetMap tiles, both free and open-source — no
 * Mapbox/Google Maps API key needed. Markers are clustered (react-leaflet-
 * cluster) since this renders up to ~3,900 real zones at once -- without
 * clustering that many overlapping circles at Sikkim-wide zoom is unreadable.
 */
// Earth-pigment hazard colours — must stay in sync with the `risk` scale
// in tailwind.config.js and with RiskLegend.jsx. "Unscored" (no ML result
// yet, api.js's capitalizeTier) gets a neutral grey, never one of the real
// risk colors -- it must never look like a real (e.g. "safe" green/low)
// assessment.
const levelColor = {
  High: "#b4472f",
  Moderate: "#c8871d",
  Low: "#5b8c4f",
  Unscored: "#8b8474",
};

function riskDivIcon(color, diameter) {
  return L.divIcon({
    className: "",
    html: `<div style="width:${diameter}px;height:${diameter}px;border-radius:50%;background:${color};opacity:0.88;border:1.5px solid rgba(255,255,255,0.65);box-shadow:0 0 2px rgba(0,0,0,0.4);"></div>`,
    iconSize: [diameter, diameter],
    iconAnchor: [diameter / 2, diameter / 2],
  });
}

// Cluster bubbles are colour-coded by the worst risk level inside them, not
// a generic count blob -- zoomed out, a judge should still see red clusters
// meaning "look here first," not lose that signal to clustering.
function createClusterIcon(cluster) {
  const children = cluster.getAllChildMarkers();
  const hasHigh = children.some((m) => m.options.riskLevel === "High");
  const hasModerate = children.some((m) => m.options.riskLevel === "Moderate");
  const color = hasHigh ? levelColor.High : hasModerate ? levelColor.Moderate : levelColor.Low;
  const count = cluster.getChildCount();
  const size = count < 10 ? 34 : count < 100 ? 42 : 52;
  return L.divIcon({
    html: `<div style="width:${size}px;height:${size}px;border-radius:50%;background:${color};opacity:0.9;border:2px solid rgba(255,255,255,0.75);display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:${size < 40 ? 12 : 13}px;box-shadow:0 1px 4px rgba(0,0,0,0.45);">${count}</div>`,
    className: "",
    iconSize: L.point(size, size, true),
  });
}

export default function RiskMap({ center, zones, height = 420 }) {
  // `center` is a fixed Sikkim-area constant from Overview.jsx, regardless of
  // the selected state -- fine while Sikkim was the only populated state, but
  // once Meghalaya went live, switching to it left the map on Sikkim/Nepal
  // with Meghalaya's markers off-screen. Averaging the zones' centres fixed
  // one state, but for "All States" the average lands in the empty gap
  // between Sikkim and Meghalaya. Fitting the map to the zones' actual
  // bounding box handles one state or all of them, with no per-state
  // coordinate table to maintain.
  const bounds =
    zones.length > 0
      ? [
          [Math.min(...zones.map((z) => z.lat)), Math.min(...zones.map((z) => z.lng))],
          [Math.max(...zones.map((z) => z.lat)), Math.max(...zones.map((z) => z.lng))],
        ]
      : null;
  // Light theme keeps the original free OpenStreetMap tiles. Dark theme uses
  // Esri's free "World Dark Gray Base" basemap so the map is not a glaring
  // white block on a dark page. CARTO's basemaps.cartocdn.com tiles (the
  // previous choice) now return a watermarked "API key required" placeholder
  // image even for anonymous requests -- verified 2026-09-06, CARTO changed
  // its free-tier policy since this was first wired up. Esri's tile service
  // is still genuinely free/keyless for this kind of use.
  const { theme } = useTheme();
  const navigate = useNavigate();
  const dark = theme === "dark";
  const tileUrl = dark
    ? "https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
    : "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
  const tileAttribution = dark
    ? '&copy; <a href="https://www.esri.com">Esri</a>, HERE, Garmin, FAO, NOAA, USGS'
    : '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

  return (
    <div style={{ height }} className="rounded-xl overflow-hidden border border-paper-200 dark:border-night-700">
      <MapContainer
        // react-leaflet's MapContainer only applies center/zoom/bounds at
        // initial mount -- changing the props on a re-render does NOT refit
        // an already-mounted map. Keying on the bounds forces a remount
        // whenever the underlying data's extent actually changes, e.g.
        // switching the selected state.
        key={bounds ? bounds.flat().map((n) => n.toFixed(2)).join(",") : "default"}
        {...(bounds
          ? { bounds, boundsOptions: { padding: [30, 30] } }
          : { center: [center.lat, center.lng], zoom: 9 })}
        scrollWheelZoom={false}
        style={{ height: "100%", width: "100%" }}
      >
        <TileLayer key={theme} attribution={tileAttribution} url={tileUrl} />
        <MarkerClusterGroup
          key={zones.length}
          chunkedLoading
          iconCreateFunction={createClusterIcon}
          maxClusterRadius={50}
        >
          {zones.map((zone) => (
            <Marker
              key={zone.id}
              position={[zone.lat, zone.lng]}
              riskLevel={zone.level}
              icon={riskDivIcon(
                levelColor[zone.level] || "#8b8474",
                zone.susceptibility != null ? 8 + zone.susceptibility * 10 : 8,
              )}
              eventHandlers={{ click: () => navigate(`/zones/${zone.id}`) }}
            >
              <Tooltip direction="top" offset={[0, -4]}>
                <strong>{zone.name}</strong>
                <br />
                Risk: {zone.level}
                {zone.susceptibility != null && ` · Susceptibility: ${(zone.susceptibility * 100).toFixed(0)}%`}
                <br />
                <em>Click for details</em>
              </Tooltip>
            </Marker>
          ))}
        </MarkerClusterGroup>
      </MapContainer>
    </div>
  );
}
