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

export default function RainfallChart({ data, thresholdMm }) {
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 10, right: 16, left: -16, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke="#e9e4d8" />
          <XAxis dataKey="day" tick={{ fontSize: 11, fill: "#8b8474" }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 11, fill: "#8b8474" }} axisLine={false} tickLine={false} unit="" />
          <Tooltip
            formatter={(value) => [`${value} mm`, "Rainfall"]}
            contentStyle={{ borderRadius: 8, border: "1px solid #e9e4d8", fontSize: 12 }}
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
