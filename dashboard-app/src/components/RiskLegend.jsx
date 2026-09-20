// Must stay in sync with `levelColor` in RiskMap.jsx and the `risk`
// scale in tailwind.config.js.
import { useTranslation } from "react-i18next";

// `key` is a translation key (severity.* / legend.unscored).
const items = [
  { key: "severity.High", color: "#b4472f" },
  { key: "severity.Moderate", color: "#c8871d" },
  { key: "severity.Low", color: "#5b8c4f" },
  { key: "legend.unscored", color: "#8b8474" },
];

export default function RiskLegend() {
  const { t } = useTranslation();
  return (
    <div className="bg-white dark:bg-night-900 rounded-lg border border-paper-200 dark:border-night-700 shadow-sm px-3 py-2 text-xs w-fit">
      <p className="text-paper-600 dark:text-paper-400">{t("legend.title")}</p>
      <p className="text-[10px] italic text-paper-500 mb-1.5">{t("legend.note")}</p>
      <div className="space-y-1">
        {items.map((it) => (
          <div key={it.key} className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: it.color }} />
            <span className="text-paper-700 dark:text-paper-300">{t(it.key)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
