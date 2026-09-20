import { useCallback, useEffect, useRef, useState } from "react";
import L from "leaflet";
import { MapContainer, TileLayer, Marker, Tooltip, useMap, useMapEvents } from "react-leaflet";
import { useNavigate } from "react-router-dom";
import "leaflet/dist/leaflet.css";
import { useTheme } from "../context/ThemeContext";
import { getMapView, getZoneStats } from "../services/api";

/**
 * RiskMap
 * -------
 * Uses Leaflet + OpenStreetMap tiles, both free and open-source — no
 * Mapbox/Google Maps API key needed.
 *
 * Two modes:
 *  - Static (`zones` passed): draws exactly those zones. Used by the zone
 *    detail page, which shows a single zone.
 *  - Dynamic (no `zones`; optional `state`): the Overview map. It never holds
 *    every zone -- with tens of thousands of real zones (and more states on
 *    the way) that would freeze the browser. Instead, each time the view
 *    changes it asks GET /zones/map for what is in view: the backend returns
 *    individual zones when few are visible, or grid clusters (count plus
 *    high/moderate/low counts) when many are. Clicking a cluster zooms into
 *    it, and the individual zones appear as you get close.
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

// Icons are cached by look: a view can hold ~1,500 zone pins, and building a
// fresh divIcon for each on every re-render is needless work.
const iconCache = new Map();
function riskDivIcon(color, diameter) {
  const key = `${color}|${diameter}`;
  if (!iconCache.has(key)) {
    iconCache.set(
      key,
      L.divIcon({
        className: "",
        html: `<div style="width:${diameter}px;height:${diameter}px;border-radius:50%;background:${color};opacity:0.88;border:1.5px solid rgba(255,255,255,0.65);box-shadow:0 0 2px rgba(0,0,0,0.4);"></div>`,
        iconSize: [diameter, diameter],
        iconAnchor: [diameter / 2, diameter / 2],
      }),
    );
  }
  return iconCache.get(key);
}

// Cluster bubbles are colour-coded by the worst risk level inside them, not
// a generic count blob -- zoomed out, a judge should still see red clusters
// meaning "look here first," not lose that signal to clustering.
function clusterDivIcon(cluster) {
  const worst = cluster.high > 0 ? "High" : cluster.moderate > 0 ? "Moderate" : cluster.low > 0 ? "Low" : "Unscored";
  const count = cluster.count;
  const size = count < 10 ? 34 : count < 100 ? 42 : count < 1000 ? 52 : 60;
  const label = count >= 10000 ? `${Math.round(count / 1000)}k` : count;
  const key = `cluster|${worst}|${size}|${label}`;
  if (!iconCache.has(key)) {
    iconCache.set(
      key,
      L.divIcon({
        html: `<div style="width:${size}px;height:${size}px;border-radius:50%;background:${levelColor[worst]};opacity:0.9;border:2px solid rgba(255,255,255,0.75);display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:${size < 40 ? 12 : 13}px;box-shadow:0 1px 4px rgba(0,0,0,0.45);">${label}</div>`,
        className: "",
        iconSize: L.point(size, size, true),
      }),
    );
  }
  return iconCache.get(key);
}

function ZoneMarker({ zone }) {
  const navigate = useNavigate();
  return (
    <Marker
      position={[zone.lat, zone.lng]}
      icon={riskDivIcon(
        levelColor[zone.level] || levelColor.Unscored,
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
  );
}

function ClusterMarker({ cluster }) {
  const map = useMap();
  return (
    <Marker
      position={[cluster.lat, cluster.lng]}
      icon={clusterDivIcon(cluster)}
      eventHandlers={{
        click: () => {
          const [minLat, minLng, maxLat, maxLng] = cluster.bounds;
          map.fitBounds([[minLat, minLng], [maxLat, maxLng]], { padding: [40, 40], maxZoom: 15 });
        },
      }}
    >
      <Tooltip direction="top" offset={[0, -8]}>
        <strong>{cluster.count.toLocaleString()} zones</strong>
        <br />
        {cluster.high.toLocaleString()} high · {cluster.moderate.toLocaleString()} moderate ·{" "}
        {cluster.low.toLocaleString()} low
        {cluster.unscored > 0 && ` · ${cluster.unscored.toLocaleString()} not yet scored`}
        <br />
        <em>Click to zoom in</em>
      </Tooltip>
    </Marker>
  );
}

// Loads and draws whatever the backend says is in the current view, and
// reloads when the user pans or zooms.
function ViewportMarkers({ state }) {
  const map = useMap();
  const [view, setView] = useState(null);
  const [failed, setFailed] = useState(false);
  // Only the most recent request may update the map: a slow response to an
  // earlier view must not overwrite a newer one.
  const latestRequest = useRef(0);

  const load = useCallback(() => {
    const b = map.getBounds();
    const id = ++latestRequest.current;
    getMapView(state, { minLat: b.getSouth(), minLng: b.getWest(), maxLat: b.getNorth(), maxLng: b.getEast() })
      .then((v) => {
        if (id !== latestRequest.current) return;
        setView(v);
        setFailed(false);
      })
      // Keep the previous pins on screen rather than blanking the map.
      .catch(() => id === latestRequest.current && setFailed(true));
  }, [map, state]);

  useEffect(() => {
    load();
  }, [load]);
  useMapEvents({ moveend: load });

  return (
    <>
      {view?.mode === "clusters" &&
        view.clusters.map((c) => <ClusterMarker key={`${c.lat},${c.lng}`} cluster={c} />)}
      {view?.mode === "zones" && view.zones.map((z) => <ZoneMarker key={z.id} zone={z} />)}
      {failed && (
        <div className="leaflet-top leaflet-right" style={{ pointerEvents: "auto" }}>
          <div className="leaflet-control rounded-lg bg-white/95 dark:bg-night-900/95 px-3 py-2 text-xs text-risk-high shadow">
            Couldn't load map data.{" "}
            <button className="underline font-medium" onClick={load}>
              Retry
            </button>
          </div>
        </div>
      )}
    </>
  );
}

function boundsOf(zones) {
  if (zones.length === 0) return null;
  const lats = zones.map((z) => z.lat);
  const lngs = zones.map((z) => z.lng);
  return [Math.min(...lats), Math.min(...lngs), Math.max(...lats), Math.max(...lngs)];
}

export default function RiskMap({ center, zones, state, height = 420 }) {
  const dynamic = zones === undefined;
  const [stats, setStats] = useState(null);

  // Dynamic mode fits its first view to where the zones actually are (the
  // stats endpoint gives that extent). It used to average the zones'
  // centres, which put "All States" in the empty gap between states.
  useEffect(() => {
    if (!dynamic) return undefined;
    let cancelled = false;
    setStats(null);
    getZoneStats(state)
      .then((s) => !cancelled && setStats(s))
      .catch(() => !cancelled && setStats({ total: 0, bounds: null }));
    return () => {
      cancelled = true;
    };
  }, [dynamic, state]);

  // Light theme keeps the original free OpenStreetMap tiles. Dark theme uses
  // Esri's free "World Dark Gray Base" basemap so the map is not a glaring
  // white block on a dark page. CARTO's basemaps.cartocdn.com tiles (the
  // previous choice) now return a watermarked "API key required" placeholder
  // image even for anonymous requests -- verified 2026-09-06, CARTO changed
  // its free-tier policy since this was first wired up. Esri's tile service
  // is still genuinely free/keyless for this kind of use.
  const { theme } = useTheme();
  const dark = theme === "dark";
  const tileUrl = dark
    ? "https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
    : "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
  const tileAttribution = dark
    ? '&copy; <a href="https://www.esri.com">Esri</a>, HERE, Garmin, FAO, NOAA, USGS'
    : '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

  // A single static zone (the detail page) keeps a fixed zoom on its centre;
  // fitting bounds around one point would zoom in as far as the map goes.
  const extent = dynamic ? stats?.bounds : zones.length > 1 ? boundsOf(zones) : null;
  if (dynamic && !stats) {
    return (
      <div style={{ height }} className="rounded-xl border border-paper-200 dark:border-night-700 flex items-center justify-center text-sm text-paper-500">
        Loading map…
      </div>
    );
  }

  return (
    <div style={{ height }} className="rounded-xl overflow-hidden border border-paper-200 dark:border-night-700">
      <MapContainer
        // react-leaflet's MapContainer only applies center/zoom/bounds at
        // initial mount -- changing the props on a re-render does NOT refit
        // an already-mounted map. Keying on the extent forces a remount
        // whenever the underlying data's location actually changes, e.g.
        // switching the selected state.
        key={extent ? extent.map((n) => n.toFixed(2)).join(",") : "default"}
        {...(extent
          ? { bounds: [[extent[0], extent[1]], [extent[2], extent[3]]], boundsOptions: { padding: [30, 30] } }
          : { center: [center.lat, center.lng], zoom: 9 })}
        scrollWheelZoom={false}
        style={{ height: "100%", width: "100%" }}
      >
        <TileLayer key={theme} attribution={tileAttribution} url={tileUrl} />
        {dynamic ? (
          <ViewportMarkers state={state} />
        ) : (
          zones.map((z) => <ZoneMarker key={z.id} zone={z} />)
        )}
      </MapContainer>
    </div>
  );
}
