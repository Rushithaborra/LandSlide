import { useMemo, useState } from "react";
import { Megaphone, Pause, Play } from "lucide-react";

/**
 * ============================================================================
 *  ALERT TICKER  —  scrolling warning strip (NEW IN DRAFT 2)
 * ============================================================================
 * Modelled on the running warning bar at the top of
 * https://mausam.imd.gov.in/responsive/rainfallinformation.php
 *
 *   [ LATEST WARNINGS ]  (i) Heavy rainfall likely over ... (ii) ...  ← scrolls
 *
 * Behaviour:
 *   • text scrolls right-to-left, forever, seamlessly
 *   • hovering (or tabbing into) the strip PAUSES it so you can read it
 *   • an explicit pause/play button for keyboard and touch users
 *   • honours prefers-reduced-motion (see src/index.css)
 *
 * ---------------------------------------------------------------------------
 * LINK SPOT I  (see src/services/api.js → getTickerBulletins)
 * ---------------------------------------------------------------------------
 * `bulletins` is passed in by DashboardLayout, which gets it from
 * `getTickerBulletins()`. That function currently returns mock text from
 * src/data/mockData.js. The backend team should point it at the real
 * warning-bulletin endpoint (Stage 5 — Notification & Alert Dispatch).
 * Nothing in THIS file needs to change when that happens.
 * ============================================================================
 */

const severityTone = {
  High: "text-risk-high",
  Moderate: "text-risk-moderate",
  Low: "text-risk-low",
};

function BulletinRun({ bulletins, ariaHidden }) {
  return (
    <div
      className="flex shrink-0 items-center"
      aria-hidden={ariaHidden ? "true" : undefined}
    >
      {bulletins.map((b, i) => (
        <span key={`${b.id}-${i}`} className="flex items-center whitespace-nowrap">
          <span className="px-6 text-[13px] italic leading-none text-ink-900">
            <span className={`mr-1.5 font-semibold not-italic ${severityTone[b.severity] || "text-ink-800"}`}>
              ({b.severity} risk)
            </span>
            {b.text}
            {b.issuedAt && (
              <span className="ml-2 not-italic text-paper-600">— {b.issuedAt}</span>
            )}
          </span>
          <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-paper-300" />
        </span>
      ))}
    </div>
  );
}

export default function AlertTicker({ bulletins = [] }) {
  const [paused, setPaused] = useState(false);

  // Longer bulletins should scroll for longer, otherwise a big batch flies
  // past unreadably. Roughly 55 characters per second of screen time.
  const duration = useMemo(() => {
    const chars = bulletins.reduce((n, b) => n + b.text.length + 24, 0);
    return `${Math.max(30, Math.round(chars / 5.5))}s`;
  }, [bulletins]);

  if (!bulletins.length) return null;

  return (
    <div className="flex items-stretch border-b border-paper-200 bg-risk-moderateSoft">
      {/* Fixed label on the left, like IMD's red "Warnings" block */}
      <div className="flex shrink-0 items-center gap-2 bg-risk-high px-4 py-2 text-white">
        <Megaphone size={14} strokeWidth={2.4} />
        <span className="text-[11px] font-semibold uppercase tracking-wider">
          Latest Warnings
        </span>
      </div>

      {/* The scrolling strip itself */}
      <div className="ticker-viewport relative flex-1 overflow-hidden">
        <div
          className="ticker-track py-2"
          style={{
            "--ticker-duration": duration,
            animationPlayState: paused ? "paused" : "running",
          }}
        >
          {/* Copy 1 is the real content; copy 2 exists only to make the loop
              seamless, so it is hidden from screen readers. */}
          <BulletinRun bulletins={bulletins} />
          <BulletinRun bulletins={bulletins} ariaHidden />
        </div>

        {/* Soft fade at the right edge so text doesn't get chopped off hard */}
        <div className="pointer-events-none absolute inset-y-0 right-0 w-10 bg-gradient-to-l from-risk-moderateSoft to-transparent" />
      </div>

      <button
        type="button"
        onClick={() => setPaused((p) => !p)}
        aria-label={paused ? "Resume scrolling warnings" : "Pause scrolling warnings"}
        className="flex shrink-0 items-center gap-1.5 border-l border-paper-300/70 px-3 text-[11px] font-medium text-ink-800 hover:bg-paper-200"
      >
        {paused ? <Play size={12} /> : <Pause size={12} />}
        <span className="hidden sm:inline">{paused ? "Play" : "Pause"}</span>
      </button>
    </div>
  );
}
