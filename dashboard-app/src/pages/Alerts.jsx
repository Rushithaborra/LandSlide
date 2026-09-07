import DashboardLayout from "../layouts/DashboardLayout";
import RecentAlertsTable from "../components/RecentAlertsTable";
import LoadError from "../components/LoadError";
import { useAsyncData } from "../hooks/useAsyncData";
import { getRecentAlerts } from "../services/api";

/**
 * LINK SPOT B/C (Stage 3 Risk Fusion + Stage 5 Notification & Alert Dispatch)
 * This table lists every alert. Hook up pagination/filtering once the real
 * `/api/alerts` endpoint supports query params (region, severity, date range).
 */
export default function Alerts() {
  const { data: alerts, error, retry } = useAsyncData(getRecentAlerts);

  return (
    <DashboardLayout title="Alerts" subtitle="All landslide risk alerts across regions">
      {error && !alerts ? (
        <LoadError message={error} onRetry={retry} />
      ) : (
        <div className="bg-white dark:bg-night-900 rounded-xl border border-paper-200 dark:border-night-700 p-4">
          <RecentAlertsTable alerts={alerts || []} />
        </div>
      )}
    </DashboardLayout>
  );
}
