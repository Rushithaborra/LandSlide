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

export default function Overview() {
  // All of this state is populated through src/services/api.js, which today
  // returns mock data and later will call the real backend. See
  // LINKING_GUIDE.md for the full hookup list.
  const [stats, setStats] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [rainfall, setRainfall] = useState([]);
  const [zones, setZones] = useState([]);

  useEffect(() => {
    getSummaryStats().then(setStats);
    getActiveAlerts().then(setAlerts);
    getRainfallTrend().then(setRainfall);
    getRiskZones().then(setZones);
  }, []);

  return (
    <DashboardLayout
      title="Overview"
      subtitle="Live summary of landslide risk and system status"
    >
      {!stats ? (
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
                <span className="text-xs text-paper-500">Sikkim</span>
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
