import { AlertTriangle } from "lucide-react";
import { Link } from "react-router-dom";

const severityStyle = {
  High: "bg-risk-highSoft dark:bg-risk-high/20 text-risk-high dark:text-risk-highOn",
  Moderate: "bg-risk-moderateSoft dark:bg-risk-moderate/20 text-risk-moderate dark:text-risk-moderateOn",
  Low: "bg-risk-lowSoft dark:bg-risk-low/20 text-risk-low dark:text-risk-lowOn",
};

export default function AlertsPanel({ alerts }) {
  return (
    <div className="bg-white dark:bg-night-900 rounded-xl border border-paper-200 dark:border-night-700 p-4 flex flex-col h-full">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-serif font-semibold text-ink-900 dark:text-paper-100 text-[15px]">Active Alerts</h2>
        <Link to="/alerts" className="text-xs font-medium text-teal-600 hover:underline">
          View all
        </Link>
      </div>

      <div className="space-y-3 flex-1">
        {alerts.map((a) => (
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

    </div>
  );
}
