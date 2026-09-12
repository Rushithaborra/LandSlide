import { useEffect, useState } from "react";
import { X, Radio, CheckCircle2 } from "lucide-react";
import { broadcastAlert } from "../services/api";

/**
 * ============================================================================
 *  BROADCAST COMPOSER MODAL — officer sends an alert out
 * ============================================================================
 * Opened from the "Broadcast" button on a row in RecentAlertsTable. Real
 * backend write (POST /alerts/{id}/broadcast, persisted in alert_broadcasts),
 * but the result always comes back status="simulated" -- no SMS/CAP/siren
 * gateway is wired up yet. That's said explicitly in the confirmation
 * banner below, not buried in a code comment, so the honesty is visible in
 * the product itself.
 * ============================================================================
 */

const CHANNELS = [
  { id: "sms", label: "Cellular SMS" },
  { id: "push", label: "Mobile app push" },
  { id: "siren", label: "Community sirens" },
  { id: "cap_gateway", label: "Govt CAP XML gateway" },
];

// This modal's severity options ("moderate"/"high"/"critical") are narrower
// than the alert list's ("Low"/"Moderate"/"High") -- a broadcast is a
// deliberate escalation, so "low" isn't a valid choice here.
function defaultSeverity(alertSeverity) {
  const s = (alertSeverity || "").toLowerCase();
  return s === "high" || s === "critical" ? s : "moderate";
}

export default function BroadcastComposerModal({ alert, onClose }) {
  const [headline, setHeadline] = useState("");
  const [severity, setSeverity] = useState("moderate");
  const [message, setMessage] = useState("");
  const [channels, setChannels] = useState(["sms", "push"]);
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!alert) return;
    setHeadline(`Landslide risk warning — ${alert.location}`);
    setSeverity(defaultSeverity(alert.severity));
    setMessage(`${alert.title}. Avoid travel through ${alert.location} until conditions improve.`);
    setChannels(["sms", "push"]);
    setResult(null);
    setError(null);
  }, [alert]);

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!alert) return null;

  const toggleChannel = (id) =>
    setChannels((prev) => (prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (channels.length === 0) return;
    setSending(true);
    setError(null);
    try {
      const broadcast = await broadcastAlert(alert.id, { headline, severity, message, channels });
      setResult(broadcast);
    } catch (err) {
      setError(err.message || "Could not send this broadcast");
    } finally {
      setSending(false);
    }
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
        aria-label="Issue alert broadcast"
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg rounded-xl border border-paper-200 bg-white shadow-2xl dark:border-night-700 dark:bg-night-900"
      >
        <div className="flex items-start justify-between gap-4 border-b border-paper-200 px-5 py-4 dark:border-night-700">
          <div className="flex items-center gap-2">
            <Radio size={17} className="text-risk-high" />
            <h2 className="font-serif text-[15px] font-semibold text-ink-900 dark:text-paper-100">
              Issue public warning broadcast
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close broadcast composer"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-paper-600 hover:bg-paper-100 dark:text-paper-400 dark:hover:bg-night-800"
          >
            <X size={17} />
          </button>
        </div>

        {result ? (
          <div className="px-5 py-6">
            <div className="flex items-start gap-3 rounded-lg bg-risk-lowSoft p-4 dark:bg-risk-low/10">
              <CheckCircle2 size={20} className="mt-0.5 shrink-0 text-risk-low" />
              <div>
                <p className="text-sm font-medium text-ink-800 dark:text-paper-200">
                  Broadcast logged for {result.channels.join(", ")}
                </p>
                <p className="mt-1 text-xs text-paper-600 dark:text-paper-400">
                  Simulated, not a real dispatch — no SMS/CAP/siren gateway is wired up yet. This
                  record is real (saved to the database); the actual send is not.
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="mt-4 w-full rounded-lg bg-ink-900 px-4 py-2 text-sm font-medium text-white hover:bg-ink-800 dark:bg-teal-600 dark:hover:bg-teal-500"
            >
              Done
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4 px-5 py-5">
            <div>
              <label className="text-[11px] font-medium uppercase tracking-wide text-paper-500">
                Alert headline
              </label>
              <input
                value={headline}
                onChange={(e) => setHeadline(e.target.value)}
                required
                className="mt-1 w-full rounded-lg border border-paper-200 bg-white px-3 py-2 text-sm text-ink-800 dark:border-night-700 dark:bg-night-800 dark:text-paper-200"
              />
            </div>

            <div>
              <label className="text-[11px] font-medium uppercase tracking-wide text-paper-500">
                Severity
              </label>
              <select
                value={severity}
                onChange={(e) => setSeverity(e.target.value)}
                className="mt-1 w-full rounded-lg border border-paper-200 bg-white px-3 py-2 text-sm text-ink-800 dark:border-night-700 dark:bg-night-800 dark:text-paper-200"
              >
                <option value="moderate">Moderate</option>
                <option value="high">High</option>
                <option value="critical">Critical (Red Alert)</option>
              </select>
            </div>

            <div>
              <label className="text-[11px] font-medium uppercase tracking-wide text-paper-500">
                Public safety guidance message
              </label>
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                required
                rows={3}
                className="mt-1 w-full rounded-lg border border-paper-200 bg-white px-3 py-2 text-sm text-ink-800 dark:border-night-700 dark:bg-night-800 dark:text-paper-200"
              />
            </div>

            <div>
              <label className="text-[11px] font-medium uppercase tracking-wide text-paper-500">
                Broadcast dispatch channels
              </label>
              <div className="mt-2 grid grid-cols-2 gap-2">
                {CHANNELS.map((c) => (
                  <label key={c.id} className="flex items-center gap-2 text-sm text-paper-700 dark:text-paper-300">
                    <input
                      type="checkbox"
                      checked={channels.includes(c.id)}
                      onChange={() => toggleChannel(c.id)}
                      className="rounded border-paper-300"
                    />
                    {c.label}
                  </label>
                ))}
              </div>
            </div>

            {error && <p className="text-sm text-risk-high">{error}</p>}

            <button
              type="submit"
              disabled={sending || channels.length === 0}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-risk-high px-4 py-2.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
            >
              <Radio size={16} />
              {sending ? "Transmitting…" : "Transmit alert broadcast"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
