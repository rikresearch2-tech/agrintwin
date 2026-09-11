import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export default function SoilTrajectoryChart({ history }) {
  if (!history || history.length === 0) {
    return (
      <p className="empty-note">
        No trajectory yet — trigger a soil-score computation to start the record.
      </p>
    );
  }

  const data = history.map((h) => ({
    date: formatDate(h.computed_at),
    score: h.score,
  }));

  return (
    <div className="trajectory-chart">
      <ResponsiveContainer width="100%" height={180}>
        <AreaChart data={data} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="scoreFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3f6b3b" stopOpacity={0.35} />
              <stop offset="100%" stopColor="#3f6b3b" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="rgba(43,33,24,0.12)" vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fontFamily: "Space Grotesk", fontSize: 12, fill: "#6b5d4c" }}
            axisLine={{ stroke: "rgba(43,33,24,0.2)" }}
            tickLine={false}
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fontFamily: "Space Grotesk", fontSize: 12, fill: "#6b5d4c" }}
            axisLine={false}
            tickLine={false}
            width={28}
          />
          <Tooltip
            contentStyle={{
              fontFamily: "Space Grotesk",
              fontSize: 12,
              background: "#f8f2e5",
              border: "1px solid rgba(43,33,24,0.2)",
              borderRadius: 2,
            }}
          />
          <Area
            type="monotone"
            dataKey="score"
            stroke="#3f6b3b"
            strokeWidth={2}
            fill="url(#scoreFill)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
