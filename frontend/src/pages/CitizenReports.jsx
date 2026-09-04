import { useEffect, useState } from "react";
import { Camera } from "lucide-react";
import DashboardLayout from "../layouts/DashboardLayout";
import { getCitizenReports, submitCitizenReport } from "../services/api";

/**
 * LINK SPOT F (Client Delivery: Citizen Reporting Form / PWA).
 * Owner: mobile/PWA team. The form below currently calls the mock
 * `submitCitizenReport` in src/services/api.js — swap that for a real
 * POST with photo upload + offline sync once the PWA backend is ready.
 */
export default function CitizenReports() {
  const [reports, setReports] = useState([]);
  const [note, setNote] = useState("");
  const [location, setLocation] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    getCitizenReports().then(setReports);
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!note || !location) return;
    setSubmitting(true);
    await submitCitizenReport({ location, note });
    setReports((prev) => [
      { id: `CR-${Math.floor(Math.random() * 900)}`, reporter: "You", location, note, status: "Pending verification", photoPlaceholder: true, submittedAt: "Just now" },
      ...prev,
    ]);
    setNote("");
    setLocation("");
    setSubmitting(false);
  };

  return (
    <DashboardLayout title="Citizen Reports" subtitle="Ground reports submitted by residents">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <form onSubmit={handleSubmit} className="bg-white rounded-xl border border-paper-200 p-4 space-y-3 h-fit">
          <h2 className="font-serif font-semibold text-ink-900 text-[15px]">Submit a report</h2>
          <input
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="Location (village, district)"
            className="w-full rounded-lg border border-paper-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-600/30"
          />
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="What did you observe?"
            rows={3}
            className="w-full rounded-lg border border-paper-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-600/30"
          />
          <button
            type="button"
            className="w-full flex items-center justify-center gap-2 rounded-lg border border-dashed border-paper-300 text-paper-500 text-sm py-2"
          >
            <Camera size={16} /> Attach photo (mock)
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-ink-900 text-white text-sm font-medium rounded-lg py-2 hover:bg-ink-800 disabled:opacity-50"
          >
            {submitting ? "Submitting…" : "Submit report"}
          </button>
        </form>

        <div className="lg:col-span-2 bg-white rounded-xl border border-paper-200 p-4">
          <h2 className="font-serif font-semibold text-ink-900 text-[15px] mb-3">Recent submissions</h2>
          <div className="space-y-3">
            {reports.map((r) => (
              <div key={r.id} className="flex gap-3 border-b border-paper-200 pb-3 last:border-0">
                <div className="w-12 h-12 rounded-lg bg-paper-100 flex items-center justify-center shrink-0 text-paper-400">
                  <Camera size={18} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium text-ink-800">{r.location}</p>
                    <span className="text-[11px] text-paper-500 whitespace-nowrap">{r.submittedAt}</span>
                  </div>
                  <p className="text-xs text-paper-600 mt-0.5">{r.note}</p>
                  <span
                    className={`inline-block mt-1.5 text-[11px] font-medium px-2 py-0.5 rounded-full ${
                      r.status === "Verified" ? "bg-risk-lowSoft text-risk-low" : "bg-risk-moderateSoft text-risk-moderate"
                    }`}
                  >
                    {r.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
