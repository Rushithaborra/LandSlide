import { useState } from "react";
import { useTranslation } from "react-i18next";
import DashboardLayout from "../layouts/DashboardLayout";
import RecentAlertsTable from "../components/RecentAlertsTable";
import LoadError from "../components/LoadError";
import ImdWarningsPanel from "../components/ImdWarningsPanel";
import RainfallHeadroomPanel from "../components/RainfallHeadroomPanel";
import BroadcastComposerModal from "../components/BroadcastComposerModal";
import { useAsyncData } from "../hooks/useAsyncData";
import { useAlertStream } from "../hooks/useAlertStream";
import { useRegion } from "../context/RegionContext";
import { getRecentAlerts, getRainfallStatus } from "../services/api";

/**
 * LINK SPOT B/C (Stage 3 Risk Fusion + Stage 5 Notification & Alert Dispatch)
 * This table lists every alert. Hook up pagination/filtering once the real
 * `/api/alerts` endpoint supports query params (region, severity, date range).
 */
export default function Alerts() {
  const { t } = useTranslation();
  const { state } = useRegion();
  const { data: alerts, error, retry } = useAsyncData(() => getRecentAlerts(state), [state]);
  const { data: rainStatus } = useAsyncData(getRainfallStatus);
  const stateName = state ? t(`states.${state}`, { defaultValue: state }) : t("states.all");
  // A state that is refreshed but not switched on for alerting has no alerts because it
  // is not monitored, not because it is safe -- say so instead of an empty table.
  const alertingOff =
    Boolean(state) && Array.isArray(rainStatus?.alerting_states) && !rainStatus.alerting_states.some((s) => s.toLowerCase() === state.toLowerCase());
  const [broadcastTarget, setBroadcastTarget] = useState(null);

  // A new alert should appear in this table the moment it fires, not only
  // when the officer happens to refresh.
  useAlertStream(retry);

  return (
    <DashboardLayout title={t("alerts.title")} subtitle={t("alerts.subtitle")}>
      <RainfallHeadroomPanel className="mb-4" />
      <ImdWarningsPanel state={state} stateName={stateName} className="mb-4" />
      {error && !alerts ? (
        <LoadError message={error} onRetry={retry} />
      ) : (
        <div className="bg-white dark:bg-night-900 rounded-xl border border-paper-200 dark:border-night-700 p-4">
          {alerts && alerts.length === 0 && (
            <p className="text-sm text-paper-500">{t(alertingOff ? "alerts.alertingOff" : "alerts.emptyForState", { state: stateName })}</p>
          )}
          <RecentAlertsTable alerts={alerts || []} onBroadcast={setBroadcastTarget} />
        </div>
      )}

      <BroadcastComposerModal alert={broadcastTarget} onClose={() => setBroadcastTarget(null)} />
    </DashboardLayout>
  );
}
