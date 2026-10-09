import { CalendarRange } from "lucide-react";
import { useTranslation } from "react-i18next";

/**
 * "Driven by 20-day rain": shown on an alert whose shortest over-the-line window is weeks
 * long, so it reflects rain accumulated over time rather than a storm happening now. A
 * neutral note, not a warning colour -- the alert itself is still valid by the system's rule.
 * Renders nothing for an alert driven by a short window.
 */
export default function LongWindowNote({ longWindow, days, className = "" }) {
  const { t } = useTranslation();
  if (!longWindow) return null;
  return (
    <p className={`flex items-center gap-1 text-paper-500 ${className}`}>
      <CalendarRange size={12} className="shrink-0" />
      {t("alertWindow.note", { days })}
    </p>
  );
}
