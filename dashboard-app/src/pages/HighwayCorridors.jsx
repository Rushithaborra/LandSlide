import { useTranslation } from "react-i18next";
import DashboardLayout from "../layouts/DashboardLayout";
import LoadError from "../components/LoadError";
import { useAsyncData } from "../hooks/useAsyncData";
import { getCorridors } from "../services/api";
import { useRegion } from "../context/RegionContext";

const severityStyle = {
  High: "bg-risk-highSoft dark:bg-risk-high/20 text-risk-high dark:text-risk-highOn",
  Moderate: "bg-risk-moderateSoft dark:bg-risk-moderate/20 text-risk-moderate dark:text-risk-moderateOn",
  Low: "bg-risk-lowSoft dark:bg-risk-low/20 text-risk-low dark:text-risk-lowOn",
  // A corridor whose zones are all unscored (see api.js capitalizeTier) --
  // deliberately neutral, never the same styling as a real risk level.
  Unscored: "bg-paper-100 dark:bg-night-800 text-paper-600 dark:text-paper-400",
};

/**
 * Real zones grouped by their real highway/road code (GET /corridors) --
 * no new data source, just the same 3,921 zones aggregated by corridor
 * instead of listed flat, so an officer can see "which road" at a glance.
 */
export default function HighwayCorridors() {
  const { t } = useTranslation();
  const { state: selectedState } = useRegion();
  const { data: corridors, error, retry } = useAsyncData(() => getCorridors(selectedState), [selectedState]);

  return (
    <DashboardLayout
      title={t("highwayCorridors.title")}
      subtitle={t("highwayCorridors.subtitle", { state: selectedState || t("overview.allStates") })}
    >
      {error && !corridors ? (
        <LoadError message={error} onRetry={retry} />
      ) : !corridors ? (
        <p className="text-sm text-paper-500">{t("common.loading")}</p>
      ) : (
        <div className="bg-white dark:bg-night-900 rounded-xl border border-paper-200 dark:border-night-700 p-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-paper-500 text-xs">
                <th className="font-medium pb-2">{t("table.corridor")}</th>
                <th className="font-medium pb-2">{t("table.zones")}</th>
                <th className="font-medium pb-2">{t("table.worstRisk")}</th>
                <th className="font-medium pb-2">{t("table.highestRiskZone")}</th>
                <th className="font-medium pb-2">{t("table.activeAlerts")}</th>
              </tr>
            </thead>
            <tbody>
              {(corridors || []).map((c) => (
                <tr key={c.code} className="border-t border-paper-200 dark:border-night-700">
                  <td className="py-2.5 pr-3 font-medium text-ink-800 dark:text-paper-200">{c.code}</td>
                  <td className="py-2.5 pr-3 text-paper-600 dark:text-paper-400">{c.zoneCount}</td>
                  <td className="py-2.5 pr-3">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${severityStyle[c.worstTier] || severityStyle.Moderate}`}>
                      {c.worstTier}
                    </span>
                  </td>
                  <td className="py-2.5 pr-3 text-paper-600 dark:text-paper-400">{c.worstZoneName}</td>
                  <td className="py-2.5 text-paper-600 dark:text-paper-400">
                    {c.activeAlertCount > 0 ? (
                      <span className="font-medium text-risk-high">{c.activeAlertCount} active</span>
                    ) : (
                      t("common.none")
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </DashboardLayout>
  );
}
