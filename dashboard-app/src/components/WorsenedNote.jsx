import { ArrowUpRight } from "lucide-react";
import { useTranslation } from "react-i18next";
import { agoLabel } from "../utils/localizedText";

/**
 * "Rain worsened 3 hours ago -- recent rain is now 2.4x the danger level": shown
 * on an alert whose rain got clearly worse after it was raised (the alert's own
 * sentence never changes). Renders nothing for an alert that has not worsened.
 */
export default function WorsenedNote({ worsenedAt, peakRatio, className = "" }) {
  const { t } = useTranslation();
  if (!worsenedAt) return null;
  return (
    <p className={`flex items-center gap-1 font-medium text-risk-high dark:text-risk-highOn ${className}`}>
      <ArrowUpRight size={12} className="shrink-0" />
      {t("alertWorse.line", { ago: agoLabel(worsenedAt, t), ratio: peakRatio == null ? "" : peakRatio.toFixed(1) })}
    </p>
  );
}
