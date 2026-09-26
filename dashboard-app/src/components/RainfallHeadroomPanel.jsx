import { Fragment, useState } from "react";
import { ChevronDown, ChevronRight, Gauge } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useAsyncData } from "../hooks/useAsyncData";
import { getRainfallHeadroom } from "../services/api";

// Green = comfortably below the line, amber = getting close, red = at or over it.
const BAND_STYLE = {
  low: "bg-risk-lowSoft text-risk-low dark:bg-risk-low/20 dark:text-risk-lowOn",
  approaching: "bg-risk-moderateSoft text-risk-moderate dark:bg-risk-moderate/20 dark:text-risk-moderateOn",
  crossed: "bg-risk-highSoft text-risk-high dark:bg-risk-high/20 dark:text-risk-highOn",
};
const bandFor = (ratio) => (ratio >= 1 ? "crossed" : ratio >= 0.75 ? "approaching" : "low");

/**
 * Every state's real rainfall against its own real threshold, all 8 at once,
 * regardless of the state selector -- so a state with 0 active alerts (because
 * nothing has crossed its line yet, not because it isn't being watched) shows
 * real proof of that, instead of an empty count speaking for itself. Uses the
 * same strongest_ratio the "rain worsened" feature already computes -- not a
 * new number invented for this panel.
 */
export default function RainfallHeadroomPanel({ className = "" }) {
  const { t } = useTranslation();
  const { data } = useAsyncData(getRainfallHeadroom);
  const [expanded, setExpanded] = useState(() => new Set());
  if (!data || data.length === 0) return null; // supplementary panel; the alerts table still works without it

  const toggle = (state) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(state) ? next.delete(state) : next.add(state);
      return next;
    });

  return (
    <div className={`rounded-xl border border-paper-200 bg-white p-4 dark:border-night-700 dark:bg-night-900 ${className}`}>
      <div className="mb-1 flex items-center gap-2">
        <Gauge size={16} className="text-teal-600" />
        <h2 className="font-serif text-[15px] font-semibold text-ink-900 dark:text-paper-100">{t("headroom.title")}</h2>
      </div>
      <p className="mb-3 text-xs text-paper-600 dark:text-paper-400">{t("headroom.note")}</p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-paper-500">
              <th className="pb-2 pr-3 font-medium">{t("table.state")}</th>
              <th className="pb-2 pr-3 font-medium">{t("headroom.status")}</th>
              <th className="pb-2 font-medium">{t("headroom.watching")}</th>
            </tr>
          </thead>
          <tbody>
            {data.map((s) => {
              const isOpen = expanded.has(s.state);
              const canExpand = s.topZones && s.topZones.length > 0;
              return (
                <Fragment key={s.state}>
                  <tr className="border-t border-paper-200 dark:border-night-700">
                    <td className="py-2 pr-3 font-medium text-ink-800 dark:text-paper-200">
                      <button
                        type="button"
                        onClick={() => canExpand && toggle(s.state)}
                        disabled={!canExpand}
                        className="flex items-center gap-1 disabled:cursor-default"
                        aria-expanded={isOpen}
                      >
                        {canExpand && (isOpen ? <ChevronDown size={14} className="text-paper-500" /> : <ChevronRight size={14} className="text-paper-500" />)}
                        {t(`states.${s.state}`, { defaultValue: s.state })}
                      </button>
                    </td>
                    <td className="py-2 pr-3">
                      {s.ratio === null ? (
                        <span className="text-paper-500">{t("headroom.noData")}</span>
                      ) : (
                        <span className={`whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${BAND_STYLE[bandFor(s.ratio)]}`}>
                          {t("headroom.percentOfLine", { pct: Math.round(s.ratio * 100) })}
                        </span>
                      )}
                    </td>
                    <td className="py-2 text-paper-600 dark:text-paper-400">{t(s.alertingEnabled ? "headroom.yes" : "headroom.no")}</td>
                  </tr>
                  {isOpen && canExpand && (
                    <tr>
                      <td colSpan={3} className="bg-paper-50 px-3 pb-3 pt-1 dark:bg-night-800">
                        <p className="mb-1.5 text-xs text-paper-500">{t("headroom.watchListNote")}</p>
                        <ul className="space-y-1">
                          {s.topZones.map((z) => (
                            <li key={z.zoneName} className="flex items-center justify-between gap-3 text-xs">
                              <span className="truncate text-paper-700 dark:text-paper-300">{z.zoneName}</span>
                              <span className={`shrink-0 whitespace-nowrap rounded-full px-2 py-0.5 font-medium ${BAND_STYLE[bandFor(z.ratio)]}`}>
                                {t("headroom.percentOfLine", { pct: Math.round(z.ratio * 100) })}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
