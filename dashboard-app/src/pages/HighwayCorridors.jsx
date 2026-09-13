import DashboardLayout from "../layouts/DashboardLayout";
import LoadError from "../components/LoadError";
import { useAsyncData } from "../hooks/useAsyncData";
import { getCorridors } from "../services/api";
import { useRegion } from "../context/RegionContext";

const severityStyle = {
  High: "bg-risk-highSoft dark:bg-risk-high/20 text-risk-high dark:text-risk-highOn",
  Moderate: "bg-risk-moderateSoft dark:bg-risk-moderate/20 text-risk-moderate dark:text-risk-moderateOn",
  Low: "bg-risk-lowSoft dark:bg-risk-low/20 text-risk-low dark:text-risk-lowOn",
};

/**
 * Real zones grouped by their real highway/road code (GET /corridors) --
 * no new data source, just the same 3,921 zones aggregated by corridor
 * instead of listed flat, so an officer can see "which road" at a glance.
 */
export default function HighwayCorridors() {
  const { state: selectedState } = useRegion();
  const { data: corridors, error, retry } = useAsyncData(() => getCorridors(selectedState), [selectedState]);

  return (
    <DashboardLayout
      title="Highway Corridors"
      subtitle={`Real zones grouped by highway, worst risk first — ${selectedState || "All States"}`}
    >
      {error && !corridors ? (
        <LoadError message={error} onRetry={retry} />
      ) : (
        <div className="bg-white dark:bg-night-900 rounded-xl border border-paper-200 dark:border-night-700 p-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-paper-500 text-xs">
                <th className="font-medium pb-2">Corridor</th>
                <th className="font-medium pb-2">Zones</th>
                <th className="font-medium pb-2">Worst risk</th>
                <th className="font-medium pb-2">Highest-risk zone</th>
                <th className="font-medium pb-2">Active alerts</th>
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
                      "None"
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
