import { Radio } from "lucide-react";

const severityStyle = {
  High: "bg-risk-highSoft dark:bg-risk-high/20 text-risk-high dark:text-risk-highOn",
  Moderate: "bg-risk-moderateSoft dark:bg-risk-moderate/20 text-risk-moderate dark:text-risk-moderateOn",
  Low: "bg-risk-lowSoft dark:bg-risk-low/20 text-risk-low dark:text-risk-lowOn",
};

export default function RecentAlertsTable({ alerts, onBroadcast }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-paper-500 text-xs">
            <th className="font-medium pb-2">Alert</th>
            <th className="font-medium pb-2">Location</th>
            <th className="font-medium pb-2">Severity</th>
            <th className="font-medium pb-2">Time</th>
            {onBroadcast && <th className="font-medium pb-2">Broadcast</th>}
          </tr>
        </thead>
        <tbody>
          {alerts.map((a) => (
            <tr key={a.id} className="border-t border-paper-200 dark:border-night-700">
              <td className="py-2.5 pr-3 text-paper-700 dark:text-paper-300">{a.title}</td>
              <td className="py-2.5 pr-3 text-paper-600 dark:text-paper-400">{a.location}</td>
              <td className="py-2.5 pr-3">
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${severityStyle[a.severity]}`}>
                  {a.severity}
                </span>
              </td>
              <td className="py-2.5 pr-3 text-paper-500 whitespace-nowrap">{a.timeAgo}</td>
              {onBroadcast && (
                <td className="py-2.5">
                  <button
                    type="button"
                    onClick={() => onBroadcast(a)}
                    aria-label={`Issue a broadcast for the alert at ${a.location}`}
                    className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-lg border border-paper-200 px-3 py-1.5 text-xs font-medium text-paper-700 hover:bg-paper-100 dark:border-night-700 dark:text-paper-300 dark:hover:bg-night-800"
                  >
                    <Radio size={13} />
                    Broadcast
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
