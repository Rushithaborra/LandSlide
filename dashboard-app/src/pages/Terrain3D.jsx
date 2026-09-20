import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import DeckGL from "@deck.gl/react";
import { TerrainLayer } from "@deck.gl/geo-layers";
import { ColumnLayer } from "@deck.gl/layers";
// Still an underscore-prefixed export in deck.gl 9.4 (@deck.gl/extensions),
// i.e. an intentionally-experimental API per deck.gl's own convention, not a
// typo -- it's the real, documented way to drape a non-terrain layer's
// points onto a TerrainLayer's actual mesh elevation.
import { _TerrainExtension as TerrainExtension } from "@deck.gl/extensions";
import { ArrowLeft } from "lucide-react";
import DashboardLayout from "../layouts/DashboardLayout";
import { getRiskZones } from "../services/api";
import { useRegion } from "../context/RegionContext";
import hillshadeBounds from "../../public/sikkim_hillshade_bounds.json";

// Phase 2 of the 3D terrain feature: a real interactive deck.gl view, built
// from the same real Copernicus GLO-30 DEM as Phase 1's static hillshade
// (scripts/generate_terrain_rgb.py encodes it as Mapbox Terrain-RGB), so the
// mesh underneath the camera is genuine elevation geometry, not a flat image
// with simulated shading. Real zone risk data (the same production
// GET /zones this dashboard already uses) is draped onto that real terrain
// via deck.gl's TerrainExtension. See README's "Phase 2" section for what
// this is and isn't verified for.
const [SOUTH, WEST] = hillshadeBounds.bounds[0];
const [NORTH, EAST] = hillshadeBounds.bounds[1];
const TERRAIN_BOUNDS = [WEST, SOUTH, EAST, NORTH];

// Mapbox Terrain-RGB decode: elevation = -10000 + R*6553.6 + G*25.6 + B*0.1
// (deck.gl's documented default decoder for this exact encoding format --
// matches scripts/generate_terrain_rgb.py's encoder one-for-one).
const ELEVATION_DECODER = { rScaler: 6553.6, gScaler: 25.6, bScaler: 0.1, offset: -10000 };

const INITIAL_VIEW_STATE = {
  longitude: (WEST + EAST) / 2,
  latitude: (SOUTH + NORTH) / 2,
  zoom: 9.3,
  pitch: 55,
  bearing: -25,
  minZoom: 7,
  maxZoom: 13,
  minPitch: 0,
  maxPitch: 80,
};

// Same real risk-tier palette as RiskMap.jsx (levelColor) and RiskLegend.jsx,
// converted to RGB triples for deck.gl.
const TIER_COLOR = {
  High: [180, 71, 47],
  Moderate: [200, 135, 29],
  Low: [91, 140, 79],
};
const UNSCORED_COLOR = [156, 163, 175];

export default function Terrain3D() {
  const { state: selectedState } = useRegion();
  const [zones, setZones] = useState([]);
  const [loadError, setLoadError] = useState(null);

  // The real DEM and terrain-RGB encoding this page renders only cover
  // Sikkim (same as Phase 1) -- always fetch Sikkim's real zones here
  // regardless of the global state selector, rather than silently trying to
  // drape another state's zones onto terrain that doesn't exist for them.
  useEffect(() => {
    getRiskZones("Sikkim")
      .then(setZones)
      .catch((err) => setLoadError(err?.message || "Could not load zone data"));
  }, []);

  const terrainLayer = useMemo(
    () =>
      new TerrainLayer({
        id: "sikkim-real-terrain",
        elevationDecoder: ELEVATION_DECODER,
        elevationData: "/sikkim_terrain_rgb.png",
        texture: "/sikkim_hillshade_overlay.png",
        bounds: TERRAIN_BOUNDS,
        color: [255, 255, 255],
        // The texture (sikkim_hillshade_overlay.png) is already a real,
        // pre-shaded hillshade -- deck.gl's default `material: true` adds
        // its own dynamic directional lighting on top of the actual mesh
        // normals, which double-shades every slope (real shadow areas from
        // the baked hillshade go nearly black under deck.gl's own shadow,
        // lit areas wash out). Disabling it lets the real, already-correct
        // shading show through cleanly.
        material: false,
        // Default meshMaxError (4.0, in real elevation meters -- the RTIN
        // simplification's error tolerance) under-resolves a mountain range
        // this large at close zoom, giving a visibly blocky/low-poly look.
        // Lower = more real geometric detail retained from the DEM.
        meshMaxError: 1.5,
      }),
    []
  );

  const zonesLayer = useMemo(
    () =>
      new ColumnLayer({
        id: "sikkim-real-zones",
        data: zones,
        getPosition: (z) => [z.lng, z.lat],
        // Real data drives the column, not a fixed decorative height: a
        // zone's actual susceptibility_score (0-1) maps to 0-900m -- tall
        // enough to read clearly against the terrain's own 0-8,560m real
        // relief without dwarfing it. diskResolution=6 gives a faceted
        // (not perfectly round) column, closer to a "data block" than a
        // cylinder.
        getElevation: (z) => (z.susceptibility || 0) * 900,
        radius: 110,
        diskResolution: 6,
        getFillColor: (z) => [...(TIER_COLOR[z.level] || UNSCORED_COLOR), 235],
        extruded: true,
        pickable: true,
        // Drapes each column's base onto the real terrain mesh's actual
        // elevation at that location, instead of starting from a flat
        // z=0 plane -- the column then rises from the real ground surface.
        extensions: [new TerrainExtension()],
      }),
    [zones]
  );

  return (
    <DashboardLayout title="3D Terrain View" subtitle="Real DEM + real zone risk data, Sikkim">
      <div className="p-4 md:p-6 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-paper-700 dark:text-paper-200 hover:underline"
          >
            <ArrowLeft size={16} /> Back to map
          </Link>
          <p className="text-xs text-paper-500 dark:text-paper-400">
            Drag to pan · Ctrl/right-click-drag to tilt &amp; rotate · scroll to zoom
          </p>
        </div>

        {selectedState && selectedState !== "Sikkim" && selectedState !== "All States" && (
          <div className="rounded-md border border-amber-300 bg-amber-50 dark:bg-amber-950/40 dark:border-amber-800 px-3 py-2 text-sm text-amber-800 dark:text-amber-200">
            The real elevation data behind this 3D view only covers Sikkim right now — showing
            Sikkim's real zones here regardless of the "{selectedState}" selector above.
          </div>
        )}

        {loadError && (
          <div className="rounded-md border border-red-300 bg-red-50 dark:bg-red-950/40 dark:border-red-800 px-3 py-2 text-sm text-red-800 dark:text-red-200">
            {loadError}
          </div>
        )}

        <div className="relative w-full overflow-hidden rounded-xl border border-paper-200 dark:border-night-700" style={{ height: "70vh" }}>
          <DeckGL
            initialViewState={INITIAL_VIEW_STATE}
            controller={{ touchRotate: true, dragRotate: true }}
            layers={[terrainLayer, zonesLayer]}
            getTooltip={({ object }) =>
              object && {
                text: `${object.name}\nRisk: ${object.level} · ${(object.susceptibility * 100).toFixed(0)}%`,
              }
            }
          />
        </div>

        <p className="text-xs text-paper-500 dark:text-paper-400">
          Real Copernicus GLO-30 DEM (elevation range 0–8,560m, matching Kanchenjunga's real
          summit) rendered as an actual 3D mesh via deck.gl's TerrainLayer — not a flat image.
          Column height is each zone's real susceptibility_score (0–1, scaled to 0–900m) from
          the same production data as the 2D map, draped onto the real terrain surface. See
          README.md's "Phase 2" section for what has and hasn't been verified on-screen.
        </p>
      </div>
    </DashboardLayout>
  );
}
