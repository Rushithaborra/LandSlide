import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import DashboardLayout from "../layouts/DashboardLayout";
import LoadError from "../components/LoadError";
import { useAsyncData } from "../hooks/useAsyncData";
import { getCorridors, getRainfallStatus } from "../services/api";
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
 * no new data source, just the same zones aggregated by corridor instead of
 * listed flat, so an officer can see "which road" at a glance.
 *
 * Two tabs: real highways (NH/SH/AH) and local named roads. Road stretches with no
 * name in OpenStreetMap are not a corridor (in Assam they are 58% of all zones) and
 * are shown as a count, not as a row. For a state where rain alerts are not switched
 * on, the alerts column says so instead of showing 0, which would read as "safe".
 */
export default function HighwayCorridors() {
  const { t } = useTranslation();
  const { state: selectedState } = useRegion();
  const { data: corridors, error, retry } = useAsyncData(() => getCorridors(selectedState), [selectedState]);
  const { data: rainStatus } = useAsyncData(getRainfallStatus);
  const [tab, setTab] = useState("highway");
  useEffect(() => setTab("highway"), [selectedState]);

  const stateName = selectedState ? t(`states.${selectedState}`, { defaultValue: selectedState }) : t("overview.allStates");
  const alertingOff =
    Boolean(selectedState) && Array.isArray(rainStatus?.alerting_states) && !rainStatus.alerting_states.some((s) => s.toLowerCase() === selectedState.toLowerCase());

  const byKind = (kind) => (corridors || []).filter((c) => c.kind === kind);
  const shown = byKind(tab);
  const unnamedZones = byKind("unnamed").reduce((n, c) => n + c.zoneCount, 0);

  const tabButton = (id) => (
    <button
      key={id}
      type="button"
      onClick={() => setTab(id)}
      className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
        tab === id
          ? "border-teal-600 bg-teal-600 text-white"
          : "border-paper-200 bg-white text-paper-600 hover:bg-paper-50 dark:border-night-700 dark:bg-night-900 dark:text-paper-400"
      }`}
    >
      {t(`highwayCorridors.tab.${id}`)} ({byKind(id).length})
    </button>
  );

  return (
    <DashboardLayout title={t("highwayCorridors.title")} subtitle={t("highwayCorridors.subtitle", { state: stateName })}>
      {error && !corridors ? (
        <LoadError message={error} onRetry={retry} />
      ) : !corridors ? (
        <p className="text-sm text-paper-500">{t("common.loading")}</p>
      ) : (
        <div className="bg-white dark:bg-night-900 rounded-xl border border-paper-200 dark:border-night-700 p-4 overflow-x-auto">
          <div className="mb-3 flex flex-wrap gap-2">{["highway", "named"].map(tabButton)}</div>

          {shown.length === 0 ? (
            <p className="text-sm text-paper-500">{t("highwayCorridors.none", { state: stateName })}</p>
          ) : (
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
                {shown.map((c) => (
                  <tr key={c.code} className="border-t border-paper-200 dark:border-night-700">
                    <td className="py-2.5 pr-3 font-medium text-ink-800 dark:text-paper-200">{c.code}</td>
                    <td className="py-2.5 pr-3 text-paper-600 dark:text-paper-400">{c.zoneCount.toLocaleString()}</td>
                    <td className="py-2.5 pr-3">
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${severityStyle[c.worstTier] || severityStyle.Moderate}`}>
                        {t(`severity.${c.worstTier}`, { defaultValue: c.worstTier })}
                      </span>
                    </td>
                    <td className="py-2.5 pr-3 text-paper-600 dark:text-paper-400">{c.worstZoneName}</td>
                    <td className="py-2.5 text-paper-600 dark:text-paper-400">
                      {alertingOff ? (
                        "—"
                      ) : c.activeAlertCount > 0 ? (
                        <span className="font-medium text-risk-high">{t("highwayCorridors.activeCount", { count: c.activeAlertCount })}</span>
                      ) : (
                        t("common.none")
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {alertingOff && <p className="mt-3 text-xs text-paper-500">{t("highwayCorridors.alertsOff", { state: stateName })}</p>}
          {unnamedZones > 0 && <p className="mt-3 text-xs text-paper-500">{t("highwayCorridors.unnamedNote", { count: unnamedZones })}</p>}
        </div>
      )}
    </DashboardLayout>
  );
}
