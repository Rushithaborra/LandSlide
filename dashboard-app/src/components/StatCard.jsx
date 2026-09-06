import { useTheme } from "../context/ThemeContext";

const trendColor = {
  up: "text-risk-high dark:text-risk-highOn",
  down: "text-risk-low dark:text-risk-lowOn",
  flat: "text-paper-600 dark:text-paper-400",
  good: "text-risk-low dark:text-risk-lowOn",
};

export default function StatCard({ icon: Icon, iconBg, iconColor, label, value, deltaLabel, trend = "flat" }) {
  // The pale icon chips are inline hex colours, so they cannot use a Tailwind
  // `dark:` class. In dark mode we tint the chip with the icon's own colour at
  // low opacity instead. Light mode keeps the original hex exactly.
  const { theme } = useTheme();
  const chipBg = theme === "dark" ? `${iconColor}26` : iconBg;

  return (
    <div className="bg-white dark:bg-night-900 rounded-xl border border-paper-200 dark:border-night-700 p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-sm text-paper-600 dark:text-paper-400">{label}</span>
        <div
          className="w-9 h-9 rounded-lg flex items-center justify-center"
          style={{ background: chipBg }}
        >
          <Icon size={18} style={{ color: iconColor }} />
        </div>
      </div>
      <div>
        <p className="text-2xl font-semibold text-ink-900 dark:text-paper-100 leading-none">{value}</p>
        <p className={`text-xs mt-2 ${trendColor[trend] || "text-paper-600"}`}>{deltaLabel}</p>
      </div>
    </div>
  );
}
