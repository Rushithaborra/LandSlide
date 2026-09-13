import { useState } from "react";
import { useTranslation } from "react-i18next";
import DashboardLayout from "../layouts/DashboardLayout";
import RecentAlertsTable from "../components/RecentAlertsTable";
import LoadError from "../components/LoadError";
import BroadcastComposerModal from "../components/BroadcastComposerModal";
import { useAsyncData } from "../hooks/useAsyncData";
import { getRecentAlerts } from "../services/api";

/**
 * LINK SPOT B/C (Stage 3 Risk Fusion + Stage 5 Notification & Alert Dispatch)
 * This table lists every alert. Hook up pagination/filtering once the real
 * `/api/alerts` endpoint supports query params (region, severity, date range).
 */
export default function Alerts() {
  const { t } = useTranslation();
  const { data: alerts, error, retry } = useAsyncData(getRecentAlerts);
  const [broadcastTarget, setBroadcastTarget] = useState(null);

  return (
    <DashboardLayout title={t("alerts.title")} subtitle={t("alerts.subtitle")}>
      {error && !alerts ? (
        <LoadError message={error} onRetry={retry} />
      ) : (
        <div className="bg-white dark:bg-night-900 rounded-xl border border-paper-200 dark:border-night-700 p-4">
          <RecentAlertsTable alerts={alerts || []} onBroadcast={setBroadcastTarget} />
        </div>
      )}

      <BroadcastComposerModal alert={broadcastTarget} onClose={() => setBroadcastTarget(null)} />
    </DashboardLayout>
  );
}
