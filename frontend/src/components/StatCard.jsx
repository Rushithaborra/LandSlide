const trendColor = {
  up: "text-risk-high",
  down: "text-risk-low",
  flat: "text-paper-600",
  good: "text-risk-low",
};

export default function StatCard({ icon: Icon, iconBg, iconColor, label, value, deltaLabel, trend = "flat" }) {
  return (
    <div className="bg-white rounded-xl border border-paper-200 p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-sm text-paper-600">{label}</span>
        <div
          className="w-9 h-9 rounded-lg flex items-center justify-center"
          style={{ background: iconBg }}
        >
          <Icon size={18} style={{ color: iconColor }} />
        </div>
      </div>
      <div>
        <p className="text-2xl font-semibold text-ink-900 leading-none">{value}</p>
        <p className={`text-xs mt-2 ${trendColor[trend] || "text-paper-600"}`}>{deltaLabel}</p>
      </div>
    </div>
  );
}
