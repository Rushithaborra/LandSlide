import { useEffect, useState } from "react";
import DashboardLayout from "../layouts/DashboardLayout";
import RecentAlertsTable from "../components/RecentAlertsTable";
import { getRecentAlerts } from "../services/api";

/**
 * LINK SPOT B/C (Stage 3 Risk Fusion + Stage 5 Notification & Alert Dispatch)
 * This table lists every alert. Hook up pagination/filtering once the real
 * `/api/alerts` endpoint supports query params (region, severity, date range).
 */
export default function Alerts() {
  const [alerts, setAlerts] = useState([]);

  useEffect(() => {
    getRecentAlerts().then(setAlerts);
  }, []);

  return (
    <DashboardLayout title="Alerts" subtitle="All landslide risk alerts across regions">
      <div className="bg-white rounded-xl border border-paper-200 p-4">
        <RecentAlertsTable alerts={alerts} />
      </div>
    </DashboardLayout>
  );
}
