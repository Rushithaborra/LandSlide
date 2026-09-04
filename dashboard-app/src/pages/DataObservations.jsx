import { useEffect, useState } from "react";
import DashboardLayout from "../layouts/DashboardLayout";
import { getDataSources } from "../services/api";

/**
 * LINK SPOT A + D (Stage 1: Raw Spatial Data Ingestion, Stage 2: GIS
 * Pre-processing). Shows whether each upstream data feed is connected.
 * Owner: data engineering team.
 */
export default function DataObservations() {
  const [sources, setSources] = useState([]);

  useEffect(() => {
    getDataSources().then(setSources);
  }, []);

  return (
    <DashboardLayout title="Data & Observations" subtitle="Upstream data source health and sync status">
      <div className="bg-white rounded-xl border border-paper-200 p-4 divide-y divide-paper-200">
        {sources.map((s) => (
          <div key={s.name} className="flex items-center justify-between py-3">
            <div>
              <p className="text-sm font-medium text-ink-800">{s.name}</p>
              <p className="text-xs text-paper-500">Last sync: {s.lastSync}</p>
            </div>
            <span
              className={`text-xs font-medium px-2.5 py-1 rounded-full ${
                s.status === "Connected"
                  ? "bg-risk-lowSoft text-risk-low"
                  : "bg-paper-100 text-paper-600"
              }`}
            >
              {s.status}
            </span>
          </div>
        ))}
      </div>
    </DashboardLayout>
  );
}
