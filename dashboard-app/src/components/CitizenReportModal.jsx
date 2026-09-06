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
} from "lucide-react";
import { verifyCitizenReport } from "../services/api";

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
          {children}
        </p>
      </div>
    </div>
  );
}

export default function CitizenReportModal({ report, onClose, onVerified }) {
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
            aria-label="Close report details"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-paper-600 hover:bg-paper-100 dark:text-paper-400 dark:hover:bg-night-800"
          >
            <X size={17} />
          </button>
        </div>

        {/* Body — photo on the left, details on the right */}
        <div className="grid grid-cols-1 gap-5 px-5 py-5 md:grid-cols-2">
          <div>
            <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-paper-500">
              Photo submitted by the citizen
            </p>
            <img
              src={report.photoUrl}
              alt={`Submitted photo for report ${report.id} at ${report.location}`}
              className="w-full rounded-lg border border-paper-200 object-cover dark:border-night-700"
            />
          </div>

          <div className="space-y-4">
            <Row icon={Compass} label="Area">
              {report.area}
            </Row>
            <Row icon={MapPin} label="Location">
              {report.location}
              <span className="block text-xs text-paper-500">
                {report.lat}, {report.lng} · {report.landmark}
              </span>
            </Row>
            <Row icon={Clock} label="Uploaded at">
              {report.submittedAt}
            </Row>
            <Row icon={User} label="Submitted by">
              {report.reporterName}
              <span className="block text-xs text-paper-500">
                {report.reporterType} · listed publicly as “{report.reporter}”
              </span>
            </Row>
            <Row icon={Phone} label="Contact">
              {report.reporterPhone}
            </Row>
            <Row icon={CloudRain} label="Weather when reported">
              {report.weatherAtReport}
            </Row>
          </div>
        </div>

        {/* Comment */}
        <div className="px-5 pb-5">
          <Row icon={MessageSquare} label="Comment from the citizen">
            {report.note}
          </Row>
        </div>

        {/* Footer — Verify sits in the right corner */}
        <div className="flex items-center justify-between gap-3 border-t border-paper-200 px-5 py-4 dark:border-night-700">
          <p className="text-[11px] leading-snug text-paper-500">
            Verify only after the area has been checked on the ground or against
            the risk map.
          </p>

          {isVerified ? (
            <span className="flex shrink-0 items-center gap-1.5 rounded-lg bg-risk-lowSoft px-3 py-2 text-sm font-medium text-risk-low dark:bg-risk-low/20 dark:text-risk-lowOn">
              <BadgeCheck size={16} />
              Verified
            </span>
          ) : (
            <button
              type="button"
              onClick={handleVerify}
              disabled={verifying}
              className="flex shrink-0 items-center gap-1.5 rounded-lg bg-ink-900 px-4 py-2 text-sm font-medium text-white hover:bg-ink-800 disabled:opacity-50 dark:bg-teal-600 dark:hover:bg-teal-500"
            >
              <BadgeCheck size={16} />
              {verifying ? "Verifying…" : "Verify report"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
