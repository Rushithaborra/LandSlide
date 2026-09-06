const severityStyle = {
  High: "bg-risk-highSoft dark:bg-risk-high/20 text-risk-high dark:text-risk-highOn",
  Moderate: "bg-risk-moderateSoft dark:bg-risk-moderate/20 text-risk-moderate dark:text-risk-moderateOn",
  Low: "bg-risk-lowSoft dark:bg-risk-low/20 text-risk-low dark:text-risk-lowOn",
};

export default function RecentAlertsTable({ alerts }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-paper-500 text-xs">
            <th className="font-medium pb-2">Alert</th>
            <th className="font-medium pb-2">Location</th>
            <th className="font-medium pb-2">Severity</th>
            <th className="font-medium pb-2">Time</th>
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
              <td className="py-2.5 text-paper-500 whitespace-nowrap">{a.timeAgo}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
