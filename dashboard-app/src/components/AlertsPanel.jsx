import { AlertTriangle } from "lucide-react";
import { Link } from "react-router-dom";

const severityStyle = {
  High: "bg-risk-highSoft text-risk-high",
  Moderate: "bg-risk-moderateSoft text-risk-moderate",
  Low: "bg-risk-lowSoft text-risk-low",
};

export default function AlertsPanel({ alerts }) {
  return (
    <div className="bg-white rounded-xl border border-paper-200 p-4 flex flex-col h-full">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-serif font-semibold text-ink-900 text-[15px]">Active Alerts</h2>
        <Link to="/alerts" className="text-xs font-medium text-teal-600 hover:underline">
          View all
        </Link>
      </div>

      <div className="space-y-3 flex-1">
        {alerts.map((a) => (
          <div key={a.id} className="flex gap-3 border-b border-paper-200 pb-3 last:border-0">
            <div className="mt-0.5 text-risk-high shrink-0">
              <AlertTriangle size={16} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-medium text-ink-800 leading-snug">{a.title}</p>
                <span className="text-[11px] text-paper-500 whitespace-nowrap">{a.timeAgo}</span>
              </div>
              <p className="text-xs text-paper-600 mt-0.5">{a.location}</p>
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

      <div className="mt-3 pt-3 border-t border-paper-200 flex items-center justify-between gap-2">
        <p className="text-[11px] text-paper-500 leading-snug">
          Alerts are based on rainfall thresholds and susceptibility analysis.
        </p>
        <Link
          to="/alerts"
          className="shrink-0 text-xs font-medium bg-ink-900 text-white px-3 py-1.5 rounded-lg hover:bg-ink-800"
        >
          Go to Alerts →
        </Link>
      </div>
    </div>
  );
}
