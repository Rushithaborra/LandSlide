const severityStyle = {
  High: "bg-risk-highSoft text-risk-high",
  Moderate: "bg-risk-moderateSoft text-risk-moderate",
  Low: "bg-risk-lowSoft text-risk-low",
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
            <tr key={a.id} className="border-t border-paper-200">
              <td className="py-2.5 pr-3 text-paper-700">{a.title}</td>
              <td className="py-2.5 pr-3 text-paper-600">{a.location}</td>
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
