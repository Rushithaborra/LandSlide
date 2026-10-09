import { Layers } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useAsyncData } from "../hooks/useAsyncData";
import { getAlertSummary } from "../services/api";

/**
 * What the active-alert count actually rests on. "102 alerts" counts road segments; segments
 * that were given identical rain data are one weather observation, and an alert driven only by
 * a weeks-long window reflects accumulated rain, not a storm now. All real counts from the
 * same rule the alert engine uses -- this panel explains the number, it never changes it.
 */
export default function AlertEvidencePanel({ state, className = "" }) {
  const { t } = useTranslation();
  const { data } = useAsyncData(() => getAlertSummary(state), [state]);
  if (!data || data.activeAlerts === 0) return null; // supplementary; the alerts table works without it

  const lines = [
    t("alertEvidence.records", { segments: data.activeAlerts, records: data.records }),
    data.longWindowAlerts > 0 && t("alertEvidence.long", { count: data.longWindowAlerts, days: data.longWindowDays }),
    data.notCurrentlyOver > 0 && t("alertEvidence.notOver", { count: data.notCurrentlyOver }),
    data.noRainfallData > 0 && t("alertEvidence.noData", { count: data.noRainfallData }),
  ].filter(Boolean);

  return (
    <div className={`rounded-xl border border-paper-200 bg-white p-4 dark:border-night-700 dark:bg-night-900 ${className}`}>
      <div className="mb-2 flex items-center gap-2">
        <Layers size={16} className="text-teal-600" />
        <h2 className="font-serif text-[15px] font-semibold text-ink-900 dark:text-paper-100">{t("alertEvidence.title")}</h2>
      </div>
      <ul className="space-y-1 text-sm text-paper-700 dark:text-paper-300">
        {lines.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-paper-500">{t("alertEvidence.note")}</p>
    </div>
  );
}
