import { useMemo, useState } from "react";
import { Megaphone, Pause, Play } from "lucide-react";
import { useTranslation } from "react-i18next";
import { agoLabel, alertSentence } from "../utils/localizedText";

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
 * `bulletins` comes from DashboardLayout → api.js getTickerBulletins(): the
 * REAL active rainfall alerts (newest first), a "+N more" item, or a "none
 * active" item that also names the states alerting is switched on for. It is
 * not an IMD bulletin feed and never shows made-up text.
 * ============================================================================
 */

const severityTone = {
  High: "text-risk-high dark:text-risk-highOn",
  Moderate: "text-risk-moderate dark:text-risk-moderateOn",
  Low: "text-risk-low dark:text-risk-lowOn",
};

const titleCase = (s) => s.charAt(0).toUpperCase() + s.slice(1);

// The fixed wording is translated here; an alert's own sentence comes from the
// backend in English (it is generated at the moment the alert is raised).
function bulletinText(b, t) {
  if (b.kind === "more") return t("ticker.more", { count: b.count });
  if (b.kind === "none") {
    const states = b.states.map(titleCase).join(", ");
    return states ? `${t("ticker.none")} ${t("ticker.noneStates", { states })}` : t("ticker.none");
  }
  return `${b.zone}: ${alertSentence(b.sentence, t, { short: true })}`;
}

function BulletinRun({ bulletins, ariaHidden }) {
  const { t } = useTranslation();
  return (
    <div
      className="flex shrink-0 items-center"
      aria-hidden={ariaHidden ? "true" : undefined}
    >
      {bulletins.map((b, i) => (
        <span key={`${b.id}-${i}`} className="flex items-center whitespace-nowrap">
          <span className="px-6 text-[13px] italic leading-none text-ink-900 dark:text-paper-100">
            {b.severity && (
              <span className={`mr-1.5 font-semibold not-italic ${severityTone[b.severity] || "text-ink-800"}`}>
                ({t(`ticker.risk.${b.severity}`, { defaultValue: b.severity })})
              </span>
            )}
            {bulletinText(b, t)}
            {b.triggeredAt && (
              <span className="ml-2 not-italic text-paper-600 dark:text-paper-400">— {agoLabel(b.triggeredAt, t)}</span>
            )}
          </span>
          <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-paper-300 dark:bg-night-700" />
        </span>
      ))}
    </div>
  );
}

export default function AlertTicker({ bulletins = [] }) {
  const { t } = useTranslation();
  const [paused, setPaused] = useState(false);

  // Longer bulletins should scroll for longer, otherwise a big batch flies
  // past unreadably. Roughly 55 characters per second of screen time.
  const duration = useMemo(() => {
    const chars = bulletins.reduce((n, b) => n + (b.sentence ? 110 : 90) + 24, 0);
    return `${Math.max(30, Math.round(chars / 5.5))}s`;
  }, [bulletins]);

  if (!bulletins.length) return null;

  return (
    <div className="flex items-stretch border-b border-paper-200 dark:border-night-700 bg-risk-moderateSoft dark:bg-[#3a3119]">
      {/* Fixed label on the left, like IMD's red "Warnings" block */}
      <div className="flex shrink-0 items-center gap-2 bg-risk-high px-4 py-2 text-white">
        <Megaphone size={14} strokeWidth={2.4} />
        <span className="text-[11px] font-semibold uppercase tracking-wider">
          {t("ticker.label")}
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
        <div className="pointer-events-none absolute inset-y-0 right-0 w-10 bg-gradient-to-l from-risk-moderateSoft dark:from-[#383018] to-transparent" />
      </div>

      <button
        type="button"
        onClick={() => setPaused((p) => !p)}
        aria-label={paused ? t("ticker.resumeAria") : t("ticker.pauseAria")}
        className="flex shrink-0 items-center gap-1.5 border-l border-paper-300/70 dark:border-night-700 px-3 text-[11px] font-medium text-ink-800 dark:text-paper-200 hover:bg-paper-200 dark:hover:bg-night-800"
      >
        {paused ? <Play size={12} /> : <Pause size={12} />}
        <span className="hidden sm:inline">{paused ? t("ticker.play") : t("ticker.pause")}</span>
      </button>
    </div>
  );
}
