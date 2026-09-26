import { Gauge } from "lucide-react";
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
  if (!data || data.length === 0) return null; // supplementary panel; the alerts table still works without it

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
            {data.map((s) => (
              <tr key={s.state} className="border-t border-paper-200 dark:border-night-700">
                <td className="py-2 pr-3 font-medium text-ink-800 dark:text-paper-200">{t(`states.${s.state}`, { defaultValue: s.state })}</td>
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
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
