import {
  ResponsiveContainer,
  BarChart,
  Bar,
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

  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 10, right: 16, left: -16, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke={grid} />
          <XAxis dataKey="day" tick={{ fontSize: 11, fill: tick }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 11, fill: tick }} axisLine={false} tickLine={false} unit="" />
          <Tooltip
            formatter={(value) => [`${value} mm`, "Rainfall"]}
            contentStyle={{ borderRadius: 8, border: `1px solid ${tooltipBorder}`, background: tooltipBg, color: tooltipText, fontSize: 12 }}
          />
          <ReferenceLine
            y={thresholdMm}
            stroke="#b4472f"
            strokeDasharray="4 4"
            label={{ value: `Threshold ${thresholdMm} mm`, position: "insideTopRight", fill: "#b4472f", fontSize: 11 }}
          />
          <Bar dataKey="mm" fill="#7ea6ac" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
