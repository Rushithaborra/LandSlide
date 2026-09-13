import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { useTranslation } from "react-i18next";
import DashboardLayout from "../layouts/DashboardLayout";
import { getIncidents, getCitizenReports } from "../services/api";
import { generateIncidentReport } from "../services/incidentReport";

const severityStyle = {
  High: "bg-risk-highSoft dark:bg-risk-high/20 text-risk-high dark:text-risk-highOn",
  Moderate: "bg-risk-moderateSoft dark:bg-risk-moderate/20 text-risk-moderate dark:text-risk-moderateOn",
  Low: "bg-risk-lowSoft dark:bg-risk-low/20 text-risk-low dark:text-risk-lowOn",
};

/**
 * LINK SPOT G — post-event incident records. Owner: backend team, once GSI
 * field-verification data is stored in PostGIS.
 *
 * DRAFT 3: this page absorbed the old Reports page. Every row now has a
 * "Download" button in the last column that builds a PDF for that incident —
 * details, weather report, rainfall trend, area history, and the citizen
 * reports filed from the same area. The PDF is produced in the browser by
 * src/services/incidentReport.js (jsPDF). See also LINK SPOT L in
 * src/services/api.js if this should become a server-rendered PDF later.
 */
export default function Incidents() {
  const { t } = useTranslation();
  const [incidents, setIncidents] = useState([]);
  const [reports, setReports] = useState([]);
  const [busyId, setBusyId] = useState(null);

  useEffect(() => {
    getIncidents().then(setIncidents);
    // getCitizenReports is a real backend call (unlike getIncidents, which is
    // mocked and can't fail) -- if it rejects, related reports just stay
    // empty for the PDF download rather than crashing the page.
    getCitizenReports().then(setReports).catch(() => {});
  }, []);

  const handleDownload = (incident) => {
    setBusyId(incident.id);
    // Citizen reports from the same area travel with the incident into the PDF.
    const related = reports.filter((r) => r.area === incident.area);
    generateIncidentReport(incident, related);
    setBusyId(null);
  };

  return (
    <DashboardLayout title={t("incidents.title")} subtitle={t("incidents.subtitle")}>
      <div className="bg-white dark:bg-night-900 rounded-xl border border-paper-200 dark:border-night-700 p-4 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-paper-500 text-xs">
              <th className="font-medium pb-2">{t("table.id")}</th>
              <th className="font-medium pb-2">{t("table.location")}</th>
              <th className="font-medium pb-2">{t("table.date")}</th>
              <th className="font-medium pb-2">{t("table.severity")}</th>
              <th className="font-medium pb-2">{t("table.status")}</th>
              <th className="font-medium pb-2">{t("table.report")}</th>
            </tr>
          </thead>
          <tbody>
            {incidents.map((i) => (
              <tr key={i.id} className="border-t border-paper-200 dark:border-night-700">
                <td className="py-2.5 pr-3 text-paper-600 dark:text-paper-400">{i.id}</td>
                <td className="py-2.5 pr-3 text-paper-700 dark:text-paper-300">{i.location}</td>
                <td className="py-2.5 pr-3 text-paper-600 dark:text-paper-400">{i.date}</td>
                <td className="py-2.5 pr-3">
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${severityStyle[i.severity]}`}>
                    {i.severity}
                  </span>
                </td>
                <td className="py-2.5 pr-3 text-paper-600 dark:text-paper-400">{i.status}</td>
                <td className="py-2.5">
                  <button
                    type="button"
                    onClick={() => handleDownload(i)}
                    disabled={busyId === i.id}
                    aria-label={t("incidents.downloadAriaLabel", { id: i.id })}
                    className="inline-flex flex-row items-center gap-1.5 whitespace-nowrap rounded-lg border border-paper-200 px-3 py-1.5 text-xs font-medium text-paper-700 hover:bg-paper-100 disabled:opacity-50 dark:border-night-700 dark:text-paper-300 dark:hover:bg-night-800"
                  >
                    <Download size={14} />
                    {t("common.download")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-xs text-paper-500">
        {t("incidents.footnote")}
      </p>
    </DashboardLayout>
  );
}
