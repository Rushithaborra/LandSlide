import { useEffect, useState } from "react";
import {
  X,
  BadgeCheck,
  MapPin,
  Clock,
  User,
  Phone,
  Compass,
  CloudRain,
  MessageSquare,
  Sparkles,
  Languages,
  Camera,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { verifyCitizenReport } from "../services/api";

// Only worth showing the translation when it actually says something
// different from the original -- an English report translated to English
// (the common case today) would just be visual clutter otherwise.
function textsDiffer(a, b) {
  if (!a || !b) return false;
  return a.trim().toLowerCase() !== b.trim().toLowerCase();
}

/**
 * ============================================================================
 *  CITIZEN REPORT MODAL  —  full detail of one report  (NEW IN DRAFT 3)
 * ============================================================================
 * Opens in the middle of the Citizen Reports page when the admin clicks any
 * row in "Recent submissions". Shows everything the citizen sent:
 *   photo, area, location, coordinates, upload time, who submitted it,
 *   their phone, the landmark, the weather at the time, and their comment.
 *
 * Two controls:
 *   • X (top right of the header) closes the modal.
 *   • "Verify report" (top right of the footer bar) marks the report verified.
 *     The status badge on the PAGE BEHIND changes to "Verified" — that is
 *     handled by the `onVerified` callback the page passes in. Every other
 *     report keeps showing "Pending verification" until it is verified too.
 *
 * LINK SPOT K (src/services/api.js) — verifyCitizenReport(id)
 *   POST /api/citizen-reports/{id}/verify
 * ============================================================================
 */

function Row({ icon: Icon, label, children }) {
  return (
    <div className="flex gap-3">
      <Icon size={15} className="mt-0.5 shrink-0 text-paper-500" />
      <div className="min-w-0">
        <p className="text-[11px] font-medium uppercase tracking-wide text-paper-500">
          {label}
        </p>
        <p className="mt-0.5 break-words text-sm text-paper-700 dark:text-paper-300">
          {children || <span className="text-paper-400">—</span>}
        </p>
      </div>
    </div>
  );
}

export default function CitizenReportModal({ report, onClose, onVerified }) {
  const { t } = useTranslation();
  const [verifying, setVerifying] = useState(false);

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!report) return null;

  const isVerified = report.status === "Verified";

  const handleVerify = async () => {
    setVerifying(true);
    await verifyCitizenReport(report.id);
    onVerified(report.id); // updates the list on the page behind this modal
    setVerifying(false);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink-950/50 p-4 dark:bg-black/70 sm:items-center"
      onClick={onClose}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Citizen report ${report.id}`}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-3xl rounded-xl border border-paper-200 bg-white shadow-2xl dark:border-night-700 dark:bg-night-900"
      >
        {/* Header — title on the left, close (X) on the right */}
        <div className="flex items-start justify-between gap-4 border-b border-paper-200 px-5 py-4 dark:border-night-700">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="font-serif text-[15px] font-semibold text-ink-900 dark:text-paper-100">
                Report {report.id}
              </h2>
              <span
                className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                  isVerified
                    ? "bg-risk-lowSoft text-risk-low dark:bg-risk-low/20 dark:text-risk-lowOn"
                    : "bg-risk-moderateSoft text-risk-moderate dark:bg-risk-moderate/20 dark:text-risk-moderateOn"
                }`}
              >
                {report.status}
              </span>
            </div>
            <p className="mt-0.5 truncate text-xs text-paper-600 dark:text-paper-400">
              {report.location}
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label={t("citizenReportModal.closeAriaLabel")}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-paper-600 hover:bg-paper-100 dark:text-paper-400 dark:hover:bg-night-800"
          >
            <X size={17} />
          </button>
        </div>

        {/* Body — photo on the left, details on the right */}
        <div className="grid grid-cols-1 gap-5 px-5 py-5 md:grid-cols-2">
          <div>
            <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-paper-500">
              {t("citizenReportModal.photoSubmitted")}
            </p>
            {report.photoUrl ? (
              <img
                src={report.photoUrl}
                alt={`Submitted photo for report ${report.id} at ${report.location}`}
                className="w-full rounded-lg border border-paper-200 object-cover dark:border-night-700"
              />
            ) : (
              <div className="flex h-48 w-full items-center justify-center rounded-lg border border-dashed border-paper-200 text-paper-400 dark:border-night-700">
                <Camera size={28} />
              </div>
            )}
          </div>

          <div className="space-y-4">
            <Row icon={Compass} label={t("citizenReportModal.area")}>
              {report.area}
            </Row>
            <Row icon={MapPin} label={t("table.location")}>
              {report.location}
              <span className="block text-xs text-paper-500">
                {report.lat}, {report.lng} · {report.landmark}
              </span>
            </Row>
            <Row icon={Clock} label={t("citizenReportModal.uploadedAt")}>
              {report.submittedAt}
            </Row>
            <Row icon={User} label={t("citizenReportModal.submittedBy")}>
              {report.reporterName}
              {report.reporterType && (
                <span className="block text-xs text-paper-500">
                  {t("citizenReportModal.listedPublicly", { reporterType: report.reporterType, reporter: report.reporter })}
                </span>
              )}
            </Row>
            <Row icon={Phone} label={t("citizenReportModal.contact")}>
              {report.reporterPhone}
            </Row>
            <Row icon={CloudRain} label={t("citizenReportModal.weatherAtReport")}>
              {report.weatherAtReport}
            </Row>
          </div>
        </div>

        {/* Comment */}
        <div className="space-y-4 px-5 pb-5">
          {report.triageSummary && (
            <Row icon={Sparkles} label={t("citizenReportModal.triageSummaryLabel")}>
              {report.triageSummary}
              <span className="mt-1 block text-[11px] font-normal text-paper-500">
                {t("citizenReportModal.triageSummaryNote")}
              </span>
            </Row>
          )}
          <Row icon={MessageSquare} label={t("citizenReportModal.commentFromCitizen")}>
            {report.note}
          </Row>
          {textsDiffer(report.note, report.descriptionTranslated) && (
            <Row icon={Languages} label={t("citizenReportModal.translationLabel")}>
              {report.descriptionTranslated}
              <span className="mt-1 block text-[11px] font-normal text-paper-500">
                {t("citizenReportModal.translationNote")}
              </span>
            </Row>
          )}
        </div>

        {/* Footer — Verify sits in the right corner */}
        <div className="flex items-center justify-between gap-3 border-t border-paper-200 px-5 py-4 dark:border-night-700">
          <p className="text-[11px] leading-snug text-paper-500">
            {t("citizenReportModal.verifyNote")}
          </p>

          {isVerified ? (
            <span className="flex shrink-0 items-center gap-1.5 rounded-lg bg-risk-lowSoft px-3 py-2 text-sm font-medium text-risk-low dark:bg-risk-low/20 dark:text-risk-lowOn">
              <BadgeCheck size={16} />
              {t("citizenReportModal.verified")}
            </span>
          ) : (
            <button
              type="button"
              onClick={handleVerify}
              disabled={verifying}
              className="flex shrink-0 items-center gap-1.5 rounded-lg bg-ink-900 px-4 py-2 text-sm font-medium text-white hover:bg-ink-800 disabled:opacity-50 dark:bg-teal-600 dark:hover:bg-teal-500"
            >
              <BadgeCheck size={16} />
              {verifying ? t("citizenReportModal.verifying") : t("citizenReportModal.verifyReport")}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
