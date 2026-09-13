import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, MapPin, Gauge, Clock } from "lucide-react";
import DashboardLayout from "../layouts/DashboardLayout";
import LoadError from "../components/LoadError";
import RainfallChart from "../components/RainfallChart";
import RecentAlertsTable from "../components/RecentAlertsTable";
import RiskMap from "../components/RiskMap";
import { useAsyncData } from "../hooks/useAsyncData";
import { getZoneById, getRainfallForZone, getAlertsForZone } from "../services/api";
import { rainfallThresholdMm } from "../data/mockData";

const severityStyle = {
  High: "bg-risk-highSoft dark:bg-risk-high/20 text-risk-high dark:text-risk-highOn",
  Moderate: "bg-risk-moderateSoft dark:bg-risk-moderate/20 text-risk-moderate dark:text-risk-moderateOn",
  Low: "bg-risk-lowSoft dark:bg-risk-low/20 text-risk-low dark:text-risk-lowOn",
};

/**
 * Drill-down reached by clicking a marker on the Overview map (see
 * RiskMap.jsx's onClick). Everything here is real data already served by
 * existing endpoints, just scoped to one zone instead of shown in
 * aggregate -- no new backend surface for this page.
 */
export default function ZoneDetail() {
  const { zoneId } = useParams();
  const navigate = useNavigate();

  const { data: zone, error: zoneError, retry: retryZone } = useAsyncData(() => getZoneById(zoneId), [zoneId]);
  const { data: rainfall } = useAsyncData(() => getRainfallForZone(zoneId), [zoneId]);
  const { data: alerts } = useAsyncData(() => getAlertsForZone(zoneId), [zoneId]);

  return (
    <DashboardLayout title="Zone Detail" subtitle="Rainfall history, alerts, and susceptibility for one zone">
      <button
        type="button"
        onClick={() => navigate(-1)}
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-paper-600 hover:text-ink-900 dark:text-paper-400 dark:hover:text-paper-100"
      >
        <ArrowLeft size={15} />
        Back
      </button>

      {zoneError && !zone ? (
        <LoadError message={zoneError} onRetry={retryZone} />
      ) : !zone ? (
        <p className="text-sm text-paper-500">Loading zone…</p>
      ) : (
        <div className="space-y-6">
          <div className="rounded-xl border border-paper-200 bg-white p-5 dark:border-night-700 dark:bg-night-900">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h2 className="font-serif text-lg font-semibold text-ink-900 dark:text-paper-100">{zone.name}</h2>
                <p className="mt-1 flex items-center gap-1.5 text-xs text-paper-500">
                  <MapPin size={13} />
                  {zone.state} · {zone.lat.toFixed(4)}, {zone.lng.toFixed(4)}
                </p>
              </div>
              <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${severityStyle[zone.level] || severityStyle.Moderate}`}>
                {zone.level} risk
              </span>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
              <div>
                <p className="flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide text-paper-500">
                  <Gauge size={12} />
                  Susceptibility
                </p>
                <p className="mt-1 text-sm font-medium text-ink-800 dark:text-paper-200">
                  {zone.susceptibility != null ? `${(zone.susceptibility * 100).toFixed(0)}%` : "Not yet scored"}
                </p>
              </div>
              <div>
                <p className="text-[11px] font-medium uppercase tracking-wide text-paper-500">Model version</p>
                <p className="mt-1 text-sm font-medium text-ink-800 dark:text-paper-200">
                  {zone.modelVersion || "—"}
                </p>
              </div>
              <div>
                <p className="flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide text-paper-500">
                  <Clock size={12} />
                  Last updated
                </p>
                <p className="mt-1 text-sm font-medium text-ink-800 dark:text-paper-200">
                  {new Date(zone.lastUpdated).toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" })}
                </p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
            <div className="xl:col-span-2 rounded-xl border border-paper-200 bg-white p-4 dark:border-night-700 dark:bg-night-900">
              <h3 className="mb-2 font-serif text-[15px] font-semibold text-ink-900 dark:text-paper-100">
                Rainfall history
              </h3>
              {!rainfall ? (
                <p className="text-sm text-paper-500">Loading…</p>
              ) : rainfall.length === 0 ? (
                <p className="text-sm text-paper-500">No rainfall data fetched for this zone yet.</p>
              ) : (
                <RainfallChart data={rainfall} thresholdMm={rainfallThresholdMm} height={260} />
              )}
            </div>

            <div className="rounded-xl border border-paper-200 bg-white p-4 dark:border-night-700 dark:bg-night-900">
              <h3 className="mb-2 font-serif text-[15px] font-semibold text-ink-900 dark:text-paper-100">Location</h3>
              <RiskMap center={{ lat: zone.lat, lng: zone.lng }} zones={[zone]} height={260} />
            </div>
          </div>

          <div className="rounded-xl border border-paper-200 bg-white p-4 dark:border-night-700 dark:bg-night-900">
            <h3 className="mb-2 font-serif text-[15px] font-semibold text-ink-900 dark:text-paper-100">
              Alerts for this zone
            </h3>
            {!alerts ? (
              <p className="text-sm text-paper-500">Loading…</p>
            ) : alerts.length === 0 ? (
              <p className="text-sm text-paper-500">No alerts have fired for this zone yet.</p>
            ) : (
              <RecentAlertsTable alerts={alerts} />
            )}
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
