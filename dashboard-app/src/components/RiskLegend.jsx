// Must stay in sync with `levelColor` in RiskMap.jsx and the `risk`
// scale in tailwind.config.js.
const items = [
  { label: "High", color: "#b4472f" },
  { label: "Moderate", color: "#c8871d" },
  { label: "Low", color: "#5b8c4f" },
];

export default function RiskLegend() {
  return (
    <div className="bg-white rounded-lg border border-paper-200 shadow-sm px-3 py-2 text-xs w-fit">
      <p className="text-paper-600 mb-1.5">Risk Level</p>
      <div className="space-y-1">
        {items.map((it) => (
          <div key={it.label} className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: it.color }} />
            <span className="text-paper-700">{it.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
