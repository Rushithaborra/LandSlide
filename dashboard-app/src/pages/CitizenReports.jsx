import { useEffect, useState } from "react";
import { Camera, ChevronRight, Sparkles } from "lucide-react";
import { useTranslation } from "react-i18next";
import DashboardLayout from "../layouts/DashboardLayout";
import CitizenReportModal from "../components/CitizenReportModal";
import LoadError from "../components/LoadError";
import { useAsyncData } from "../hooks/useAsyncData";
import { useRegion } from "../context/RegionContext";
import { getCitizenReports } from "../services/api";

/**
 * LINK SPOT F (Client Delivery: Citizen Reporting Form / PWA).
 * Owner: mobile/PWA team.
 *
 * DRAFT 3 CHANGES:
 *  - the "Submit a report" form was removed (citizens submit from the PWA,
 *    not from the admin dashboard), so the submissions list is now centred
 *    and fills the page instead of leaving an empty column.
 *  - clicking a submission opens CitizenReportModal with the full detail and
 *    a "Verify report" button. Verifying updates the badge in THIS list.
 */
export default function CitizenReports() {
  const { t } = useTranslation();
  const { state } = useRegion();
  const { data, error, retry } = useAsyncData(() => getCitizenReports(state), [state]);
  const stateName = state ? t(`states.${state}`, { defaultValue: state }) : t("states.all");
  const [reports, setReports] = useState([]);
  const [selectedId, setSelectedId] = useState(null);

  // Mirrored into local state (rather than read straight from the hook) so
  // handleVerified below can optimistically flip one report's badge without
  // waiting on a re-fetch.
  useEffect(() => {
    if (data) setReports(data);
  }, [data]);

  // Flip one report to "Verified" in the list behind the modal.
  const handleVerified = (id) =>
    setReports((prev) =>
      prev.map((r) => (r.id === id ? { ...r, status: "Verified" } : r))
    );

  const selected = reports.find((r) => r.id === selectedId) || null;

  return (
    <DashboardLayout
      title={t("citizenReports.title")}
      subtitle={t("citizenReports.subtitle")}
    >
      {error && !data ? (
        <LoadError message={error} onRetry={retry} />
      ) : (
      <>
      {/* Centred column — takes the space the submit form used to occupy */}
      <div className="mx-auto w-full max-w-4xl">
        <div className="rounded-xl border border-paper-200 bg-white p-5 dark:border-night-700 dark:bg-night-900">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-serif text-[15px] font-semibold text-ink-900 dark:text-paper-100">
              {t("citizenReports.recentSubmissions")}
            </h2>
            <span className="text-xs text-paper-500">
              {t("citizenReports.reportCount", { count: reports.length })}
            </span>
          </div>

          {data && reports.length === 0 && (
            <p className="text-sm text-paper-500">{t("citizenReports.noneForState", { state: stateName })}</p>
          )}

          <div className="divide-y divide-paper-200 dark:divide-night-700">
            {reports.map((r) => (
              <button
                key={r.id}
                type="button"
                onClick={() => setSelectedId(r.id)}
                aria-label={t("citizenReports.openDetailsAriaLabel", { id: r.id })}
                className="flex w-full items-start gap-4 py-4 text-left first:pt-0 last:pb-0 hover:bg-paper-50 dark:hover:bg-night-800"
              >
                <div className="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-paper-100 text-paper-400 dark:bg-night-800">
                  {r.photoUrl ? (
                    <img
                      src={r.photoUrl}
                      alt=""
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <Camera size={18} />
                  )}
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium text-ink-800 dark:text-paper-200">
                      {r.location}
                    </p>
                    <span className="whitespace-nowrap text-[11px] text-paper-500">
                      {r.submittedAt}
                    </span>
                  </div>
                  {r.triageSummary && (
                    <p className="mt-0.5 flex items-start gap-1 text-xs font-medium text-teal-700 dark:text-teal-400">
                      <Sparkles size={12} className="mt-0.5 shrink-0" />
                      <span>{r.triageSummary}</span>
                    </p>
                  )}
                  <p className="mt-0.5 text-xs text-paper-600 dark:text-paper-400">
                    {r.note}
                  </p>
                  <span
                    className={`mt-1.5 inline-block rounded-full px-2 py-0.5 text-[11px] font-medium ${
                      r.status === "Verified"
                        ? "bg-risk-lowSoft text-risk-low dark:bg-risk-low/20 dark:text-risk-lowOn"
                        : "bg-risk-moderateSoft text-risk-moderate dark:bg-risk-moderate/20 dark:text-risk-moderateOn"
                    }`}
                  >
                    {r.status}
                  </span>
                </div>

                <ChevronRight
                  size={16}
                  className="mt-1 shrink-0 text-paper-400"
                />
              </button>
            ))}
          </div>

          <p className="mt-4 text-xs text-paper-500">{t("citizenReports.stateNote")}</p>
        </div>
      </div>

      <CitizenReportModal
        report={selected}
        onClose={() => setSelectedId(null)}
        onVerified={handleVerified}
      />
      </>
      )}
    </DashboardLayout>
  );
}
