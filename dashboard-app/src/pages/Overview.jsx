import { useEffect, useState } from "react";
import { AlertTriangle, Bell, Users, CloudRain, ShieldCheck } from "lucide-react";
import DashboardLayout from "../layouts/DashboardLayout";
import StatCard from "../components/StatCard";
import RiskMap from "../components/RiskMap";
import RiskLegend from "../components/RiskLegend";
import AlertsPanel from "../components/AlertsPanel";
import RainfallChart from "../components/RainfallChart";
import {
  getSummaryStats,
  getActiveAlerts,
  getRainfallTrend,
  getRiskZones,
} from "../services/api";
import { mapCenter, rainfallThresholdMm } from "../data/mockData";
import { useRegion } from "../context/RegionContext";

export default function Overview() {
  // All of this state is populated through src/services/api.js, which today
  // returns mock data and later will call the real backend. See
  // LINKING_GUIDE.md for the full hookup list.
  const [stats, setStats] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [rainfall, setRainfall] = useState([]);
  const [zones, setZones] = useState([]);
  const [loadError, setLoadError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  const { state: selectedState } = useRegion();

  useEffect(() => {
    // Previously each call was a bare .then(setX) with no .catch() -- if any
    // one of these rejected (a transient network blip, the backend briefly
    // restarting mid-deploy), `stats` stayed null forever and the page sat
    // on "Loading overview..." permanently with no error and no way to
    // retry short of a manual refresh. Promise.allSettled + an explicit
    // error state fixes both: a partial failure still unblocks the page,
    // and a full failure shows a real retry button.
    let cancelled = false;
    setLoadError(null);

    Promise.allSettled([
      getSummaryStats(selectedState),
      getActiveAlerts(),
      getRainfallTrend(selectedState),
      getRiskZones(selectedState),
    ]).then(([statsR, alertsR, rainfallR, zonesR]) => {
      if (cancelled) return;
      if (statsR.status === "fulfilled") setStats(statsR.value);
      if (alertsR.status === "fulfilled") setAlerts(alertsR.value);
      if (rainfallR.status === "fulfilled") setRainfall(rainfallR.value);
      if (zonesR.status === "fulfilled") setZones(zonesR.value);
      if (statsR.status === "rejected") {
        setLoadError(statsR.reason?.message || "Could not reach the backend");
      }
    });

    return () => {
      cancelled = true;
    };
  }, [retryCount, selectedState]);

  return (
    <DashboardLayout
      title="Overview"
      subtitle="Live summary of landslide risk and system status"
    >
      {!stats && loadError ? (
        <div className="rounded-xl border border-risk-high/30 bg-risk-highSoft dark:bg-risk-high/10 p-5">
          <p className="text-sm font-medium text-risk-high">Couldn't load the overview</p>
          <p className="text-sm text-paper-500 mt-1">{loadError}</p>
          <button
            onClick={() => setRetryCount((n) => n + 1)}
            className="mt-3 text-sm font-medium px-3 py-1.5 rounded-lg bg-risk-high text-white hover:opacity-90"
          >
            Retry
          </button>
        </div>
      ) : !stats ? (
        <p className="text-sm text-paper-500">Loading overview…</p>
      ) : (
        <div className="space-y-6">
          {/* Top stat cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-4">
            <StatCard
              icon={AlertTriangle}
              iconBg="#f8ebe6"
              iconColor="#b4472f"
              label="High Risk Zones"
              value={stats.highRiskZones.value}
              deltaLabel={stats.highRiskZones.deltaLabel}
              trend={stats.highRiskZones.trend}
            />
            <StatCard
              icon={Bell}
              iconBg="#faf0dd"
              iconColor="#c8871d"
              label="Active Alerts"
              value={stats.activeAlerts.value}
              deltaLabel={stats.activeAlerts.deltaLabel}
              trend={stats.activeAlerts.trend}
            />
            <StatCard
              icon={Users}
              iconBg="#e7eef2"
              iconColor="#3a6b82"
              label="Affected Villages"
              value={stats.affectedVillages.value}
              deltaLabel={stats.affectedVillages.deltaLabel}
              trend={stats.affectedVillages.trend}
            />
            <StatCard
              icon={CloudRain}
              iconBg="#e9f2f2"
              iconColor="#15606b"
              label="Rainfall (24h)"
              value={stats.rainfall24h.value}
              deltaLabel={stats.rainfall24h.deltaLabel}
              trend={stats.rainfall24h.trend}
            />
            <StatCard
              icon={ShieldCheck}
              iconBg="#ecf2e8"
              iconColor="#5b8c4f"
              label="System Health"
              value={stats.systemHealth.value}
              deltaLabel={stats.systemHealth.deltaLabel}
              trend={stats.systemHealth.trend}
            />
          </div>

          {/* Map + Active alerts */}
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            <div className="xl:col-span-2 bg-white dark:bg-night-900 rounded-xl border border-paper-200 dark:border-night-700 p-4">
              <div className="flex items-center justify-between mb-3">
                <h2 className="font-serif font-semibold text-ink-900 dark:text-paper-100 text-[15px]">Landslide Risk Map</h2>
                <span className="text-xs text-paper-500">{selectedState || "All States"}</span>
              </div>
              <div className="relative z-0">
                <RiskMap center={mapCenter} zones={zones} />
                <div className="absolute left-3 bottom-3 z-[400]">
                  <RiskLegend />
                </div>
              </div>
            </div>

            <AlertsPanel alerts={alerts} />
          </div>

          {/* Rainfall trend — full width.
              DRAFT 3: the "Recent Alerts" card that used to sit beside this
              was removed, so the chart now takes the whole row. */}
          <div className="bg-white rounded-xl border border-paper-200 p-5 dark:bg-night-900 dark:border-night-700">
            <div className="flex items-center justify-between mb-2">
              <h2 className="font-serif font-semibold text-ink-900 text-[15px] dark:text-paper-100">
                Rainfall Trend (Last 7 Days)
              </h2>
              <span className="text-xs text-paper-500">
                Danger threshold {rainfallThresholdMm} mm
              </span>
            </div>
            <RainfallChart data={rainfall} thresholdMm={rainfallThresholdMm} height={340} />
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
