import { AlertTriangle } from "lucide-react";
import { Link } from "react-router-dom";

const severityStyle = {
  High: "bg-risk-highSoft dark:bg-risk-high/20 text-risk-high dark:text-risk-highOn",
  Moderate: "bg-risk-moderateSoft dark:bg-risk-moderate/20 text-risk-moderate dark:text-risk-moderateOn",
  Low: "bg-risk-lowSoft dark:bg-risk-low/20 text-risk-low dark:text-risk-lowOn",
};

// This panel sits in a fixed-height sidebar next to the map on Overview --
// with real alert volume (51 active, at real Sikkim scale) rendering every
// one unbounded made the whole page ~20,000px tall, since nothing here ever
// scrolled or capped. Showing the 5 most recent (the full list is one click
// away via "View all") keeps the sidebar the same height as the map instead
// of dictating the whole page's length.
const VISIBLE_COUNT = 5;

export default function AlertsPanel({ alerts }) {
  const visible = alerts.slice(0, VISIBLE_COUNT);
  const remaining = alerts.length - visible.length;

  return (
    <div className="bg-white dark:bg-night-900 rounded-xl border border-paper-200 dark:border-night-700 p-4 flex flex-col h-full">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-serif font-semibold text-ink-900 dark:text-paper-100 text-[15px]">Active Alerts</h2>
        <Link to="/alerts" className="text-xs font-medium text-teal-600 hover:underline">
          View all
        </Link>
      </div>

      <div className="space-y-3 flex-1 overflow-y-auto">
        {visible.map((a) => (
          <div key={a.id} className="flex gap-3 border-b border-paper-200 dark:border-night-700 pb-3 last:border-0">
            <div className="mt-0.5 text-risk-high dark:text-risk-highOn shrink-0">
              <AlertTriangle size={16} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-medium text-ink-800 dark:text-paper-200 leading-snug">{a.title}</p>
                <span className="text-[11px] text-paper-500 whitespace-nowrap">{a.timeAgo}</span>
              </div>
              <p className="text-xs text-paper-600 dark:text-paper-400 mt-0.5">{a.location}</p>
              <span
                className={`inline-block mt-1.5 text-[11px] font-medium px-2 py-0.5 rounded-full ${
                  severityStyle[a.severity] || "bg-paper-100 text-paper-600"
                }`}
              >
                {a.severity}
              </span>
            </div>
          </div>
        ))}
      </div>

      {remaining > 0 && (
        <Link
          to="/alerts"
          className="mt-3 block text-center text-xs font-medium text-paper-600 hover:text-teal-600 dark:text-paper-400"
        >
          +{remaining} more active alert{remaining === 1 ? "" : "s"}
        </Link>
      )}

    </div>
  );
}
