import { useEffect, useState } from "react";
import DashboardLayout from "../layouts/DashboardLayout";
import RiskMap from "../components/RiskMap";
import RiskLegend from "../components/RiskLegend";
import { getRiskZones } from "../services/api";
import { mapCenter } from "../data/mockData";

/**
 * LINK SPOT E (Stage 3: Two-Tier Risk Modeling & Scoring)
 * This page currently shows mock circle markers. Once the ML team's
 * susceptibility raster / GeoJSON is served from the backend, this is the
 * place to render it as a proper heatmap layer instead of CircleMarkers.
 * A good free option: `react-leaflet-heatmap-layer-v3` or a GeoJSON polygon
 * layer, both work with the same free Leaflet/OpenStreetMap setup used here.
 */
export default function LiveMap() {
  const [zones, setZones] = useState([]);

  useEffect(() => {
    getRiskZones().then(setZones);
  }, []);

  return (
    <DashboardLayout title="Live Map" subtitle="Full-screen landslide susceptibility view">
      <div className="bg-white rounded-xl border border-paper-200 p-4">
        <div className="relative">
          <RiskMap center={mapCenter} zones={zones} height={640} />
          <div className="absolute left-3 bottom-3 z-[400]">
            <RiskLegend />
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
