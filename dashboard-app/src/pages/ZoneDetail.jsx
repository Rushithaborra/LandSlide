import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, MapPin, Gauge, Clock, Navigation } from "lucide-react";
import { useTranslation } from "react-i18next";
import DashboardLayout from "../layouts/DashboardLayout";
import LoadError from "../components/LoadError";
import RainfallChart from "../components/RainfallChart";
import RecentAlertsTable from "../components/RecentAlertsTable";
import RiskMap from "../components/RiskMap";
import { useAsyncData } from "../hooks/useAsyncData";
import { getZoneById, getRainfallForZone, getAlertsForZone, getNearestSafeZone } from "../services/api";

const severityStyle = {
  High: "bg-risk-highSoft dark:bg-risk-high/20 text-risk-high dark:text-risk-highOn",
  Moderate: "bg-risk-moderateSoft dark:bg-risk-moderate/20 text-risk-moderate dark:text-risk-moderateOn",
  Low: "bg-risk-lowSoft dark:bg-risk-low/20 text-risk-low dark:text-risk-lowOn",
  // No real tier match -- deliberately neutral, never the same styling as
  // a real risk level (see api.js capitalizeTier).
  Unscored: "bg-paper-100 dark:bg-night-800 text-paper-600 dark:text-paper-400",
};

/**
 * Drill-down reached by clicking a marker on the Overview map (see
 * RiskMap.jsx's onClick). Everything here is real data already served by
 * existing endpoints, just scoped to one zone instead of shown in
 * aggregate -- no new backend surface for this page.
 */
export default function ZoneDetail() {
  const { t } = useTranslation();
  const { zoneId } = useParams();
  const navigate = useNavigate();

  const { data: zone, error: zoneError, retry: retryZone } = useAsyncData(() => getZoneById(zoneId), [zoneId]);
  const { data: rainfall } = useAsyncData(() => getRainfallForZone(zoneId), [zoneId]);
  const { data: alerts } = useAsyncData(() => getAlertsForZone(zoneId), [zoneId]);
  // null while loading, undefined-safe "no safer zone found" is represented
  // as an explicit null result from getNearestSafeZone itself, not this.
  const { data: nearestSafe } = useAsyncData(
    () => (zone ? getNearestSafeZone(zone) : Promise.resolve(null)),
    [zone?.id],
  );

  return (
    <DashboardLayout title={t("zoneDetail.title")} subtitle={t("zoneDetail.subtitle")}>
      <button
        type="button"
        onClick={() => navigate(-1)}
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-paper-600 hover:text-ink-900 dark:text-paper-400 dark:hover:text-paper-100"
      >
        <ArrowLeft size={15} />
        {t("common.back")}
      </button>

      {zoneError && !zone ? (
        <LoadError message={zoneError} onRetry={retryZone} />
      ) : !zone ? (
        <p className="text-sm text-paper-500">{t("zoneDetail.loadingZone")}</p>
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
                {zone.level === "Unscored" ? t("zoneDetail.notYetScored") : t("zoneDetail.risk", { level: zone.level })}
              </span>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
              <div>
                <p className="flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide text-paper-500">
                  <Gauge size={12} />
                  {t("zoneDetail.susceptibility")}
                </p>
                <p className="mt-1 text-sm font-medium text-ink-800 dark:text-paper-200">
                  {zone.susceptibility != null ? `${(zone.susceptibility * 100).toFixed(0)}%` : t("zoneDetail.notYetScored")}
                </p>
              </div>
              <div>
                <p className="text-[11px] font-medium uppercase tracking-wide text-paper-500">{t("zoneDetail.modelVersion")}</p>
                <p className="mt-1 text-sm font-medium text-ink-800 dark:text-paper-200">
                  {zone.modelVersion || "—"}
                </p>
              </div>
              <div>
                <p className="flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide text-paper-500">
                  <Clock size={12} />
                  {t("zoneDetail.lastUpdated")}
                </p>
                <p className="mt-1 text-sm font-medium text-ink-800 dark:text-paper-200">
                  {new Date(zone.lastUpdated).toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" })}
                </p>
              </div>
              <div>
                <p className="flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide text-paper-500">
                  <Navigation size={12} />
                  {t("zoneDetail.nearestSafer")}
                </p>
                {zone.level === "Low" ? (
                  <p className="mt-1 text-sm text-paper-500">{t("zoneDetail.alreadyLowest")}</p>
                ) : nearestSafe === undefined ? (
                  <p className="mt-1 text-sm text-paper-500">{t("common.loading")}</p>
                ) : nearestSafe === null ? (
                  <p className="mt-1 text-sm text-paper-500">{t("zoneDetail.noSaferNearby")}</p>
                ) : (
                  <a
                    href={`https://www.google.com/maps/dir/?api=1&origin=${zone.lat},${zone.lng}&destination=${nearestSafe.lat},${nearestSafe.lng}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-1 flex items-center gap-1 text-sm font-medium text-teal-700 hover:underline dark:text-teal-400"
                  >
                    {t("zoneDetail.saferZoneLink", {
                      name: nearestSafe.name,
                      km: nearestSafe.distanceKm.toFixed(1),
                      level: nearestSafe.level,
                    })}
                  </a>
                )}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
            <div className="xl:col-span-2 rounded-xl border border-paper-200 bg-white p-4 dark:border-night-700 dark:bg-night-900">
              <h3 className="mb-2 font-serif text-[15px] font-semibold text-ink-900 dark:text-paper-100">
                {t("zoneDetail.rainfallHistory")}
              </h3>
              {!rainfall ? (
                <p className="text-sm text-paper-500">{t("common.loading")}</p>
              ) : rainfall.readings.length === 0 ? (
                <p className="text-sm text-paper-500">{t("zoneDetail.noRainfallData")}</p>
              ) : (
                <RainfallChart data={rainfall.readings} thresholdMm={rainfall.threshold?.mm ?? null} height={260} />
              )}
            </div>

            <div className="rounded-xl border border-paper-200 bg-white p-4 dark:border-night-700 dark:bg-night-900">
              <h3 className="mb-2 font-serif text-[15px] font-semibold text-ink-900 dark:text-paper-100">{t("table.location")}</h3>
              <RiskMap center={{ lat: zone.lat, lng: zone.lng }} zones={[zone]} height={260} />
            </div>
          </div>

          <div className="rounded-xl border border-paper-200 bg-white p-4 dark:border-night-700 dark:bg-night-900">
            <h3 className="mb-2 font-serif text-[15px] font-semibold text-ink-900 dark:text-paper-100">
              {t("zoneDetail.alertsForZone")}
            </h3>
            {!alerts ? (
              <p className="text-sm text-paper-500">{t("common.loading")}</p>
            ) : alerts.length === 0 ? (
              <p className="text-sm text-paper-500">{t("zoneDetail.noAlerts")}</p>
            ) : (
              <RecentAlertsTable alerts={alerts} />
            )}
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
