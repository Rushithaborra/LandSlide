import { useEffect, useState } from "react";
import DashboardLayout from "../layouts/DashboardLayout";
import { getIncidents } from "../services/api";

const severityStyle = {
  High: "bg-risk-highSoft text-risk-high",
  Moderate: "bg-risk-moderateSoft text-risk-moderate",
  Low: "bg-risk-lowSoft text-risk-low",
};

/**
 * LINK SPOT G — post-event incident records. Owner: backend team, once GSI
 * field-verification data is stored in PostGIS.
 */
export default function Incidents() {
  const [incidents, setIncidents] = useState([]);

  useEffect(() => {
    getIncidents().then(setIncidents);
  }, []);

  return (
    <DashboardLayout title="Incidents" subtitle="Verified landslide incidents log">
      <div className="bg-white rounded-xl border border-paper-200 p-4 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-paper-500 text-xs">
              <th className="font-medium pb-2">ID</th>
              <th className="font-medium pb-2">Location</th>
              <th className="font-medium pb-2">Date</th>
              <th className="font-medium pb-2">Severity</th>
              <th className="font-medium pb-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {incidents.map((i) => (
              <tr key={i.id} className="border-t border-paper-200">
                <td className="py-2.5 pr-3 text-paper-600">{i.id}</td>
                <td className="py-2.5 pr-3 text-paper-700">{i.location}</td>
                <td className="py-2.5 pr-3 text-paper-600">{i.date}</td>
                <td className="py-2.5 pr-3">
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${severityStyle[i.severity]}`}>
                    {i.severity}
                  </span>
                </td>
                <td className="py-2.5 text-paper-600">{i.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </DashboardLayout>
  );
}
