import { MapContainer, TileLayer, CircleMarker, Tooltip } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { useTheme } from "../context/ThemeContext";

/**
 * RiskMap
 * -------
 * LINK SPOT E (see src/services/api.js and LINKING_GUIDE.md):
 * `zones` should come from the Stage 3 Risk Engine Fusion output
 * (GET /api/risk-zones). Right now the parent page passes mock zones.
 *
 * Uses Leaflet + OpenStreetMap tiles, both free and open-source — no
 * Mapbox/Google Maps API key needed. Swap the TileLayer `url` below for a
 * different free provider (e.g. CARTO, Stadia) if a different basemap style
 * is wanted later.
 */
// Earth-pigment hazard colours — must stay in sync with the `risk` scale
// in tailwind.config.js and with RiskLegend.jsx.
const levelColor = {
  High: "#b4472f",
  Moderate: "#c8871d",
  Low: "#5b8c4f",
};

export default function RiskMap({ center, zones, height = 420 }) {
  // Light theme keeps the original free OpenStreetMap tiles. Dark theme uses
  // CARTO's free "dark_all" basemap so the map is not a glaring white block
  // on a dark page. Neither provider needs an API key.
  const { theme } = useTheme();
  const dark = theme === "dark";
  const tileUrl = dark
    ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
    : "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
  const tileAttribution = dark
    ? '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
    : '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

  return (
    <div style={{ height }} className="rounded-xl overflow-hidden border border-paper-200 dark:border-night-700">
      <MapContainer
        center={[center.lat, center.lng]}
        zoom={9}
        scrollWheelZoom={false}
        style={{ height: "100%", width: "100%" }}
      >
        <TileLayer key={theme} attribution={tileAttribution} url={tileUrl} />
        {zones.map((zone) => (
          <CircleMarker
            key={zone.id}
            center={[zone.lat, zone.lng]}
            radius={10 + zone.susceptibility * 14}
            pathOptions={{
              color: levelColor[zone.level] || "#8b8474",
              fillColor: levelColor[zone.level] || "#8b8474",
              fillOpacity: 0.45,
              weight: 1.5,
            }}
          >
            <Tooltip direction="top" offset={[0, -4]}>
              <strong>{zone.name}</strong>
              <br />
              Risk: {zone.level} · Susceptibility: {(zone.susceptibility * 100).toFixed(0)}%
            </Tooltip>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
}
