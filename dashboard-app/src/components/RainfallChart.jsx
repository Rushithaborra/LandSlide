import {
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from "recharts";
import { useTheme } from "../context/ThemeContext";

export default function RainfallChart({ data, thresholdMm, height = 256 }) {
  // Recharts colours are props, not CSS classes, so the theme is read here.
  // The light values are exactly the ones used before.
  const { theme } = useTheme();
  const dark = theme === "dark";
  const grid = dark ? "#2c3733" : "#e9e4d8";
  const tick = dark ? "#8b8474" : "#8b8474";
  const tooltipBg = dark ? "#1c2420" : "#ffffff";
  const tooltipBorder = dark ? "#35413a" : "#e9e4d8";
  const tooltipText = dark ? "#f5f2ea" : "#1f2320";
  const observedColor = "#7ea6ac";
  const forecastColor = dark ? "#3f5a5e" : "#c3dade";
  const hasForecast = data.some((d) => d.isForecast);

  return (
    <div style={{ height }}>
      {hasForecast && (
        <div className="mb-1 flex items-center justify-end gap-1.5 text-[11px] text-paper-500">
          <span className="inline-block h-2 w-2 rounded-sm" style={{ background: forecastColor }} />
          Lighter bar = forecast, not yet observed
        </div>
      )}
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 10, right: 16, left: -16, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke={grid} />
          <XAxis dataKey="day" tick={{ fontSize: 11, fill: tick }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 11, fill: tick }} axisLine={false} tickLine={false} unit="" />
          <Tooltip
            formatter={(value, name, props) => [
              `${value} mm${props.payload.isForecast ? " (forecast)" : ""}`,
              "Rainfall",
            ]}
            contentStyle={{ borderRadius: 8, border: `1px solid ${tooltipBorder}`, background: tooltipBg, color: tooltipText, fontSize: 12 }}
          />
          {thresholdMm != null && (
            <ReferenceLine
              y={thresholdMm}
              stroke="#b4472f"
              strokeDasharray="4 4"
              label={{ value: `Threshold ${thresholdMm} mm`, position: "insideTopRight", fill: "#b4472f", fontSize: 11 }}
            />
          )}
          <Bar dataKey="mm" radius={[4, 4, 0, 0]}>
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.isForecast ? forecastColor : observedColor} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
