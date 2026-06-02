"use client";

import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";

interface PnLChartProps {
  data: { time: string; value: number; pnl?: number }[];
  height?: number;
  color?: string;
  valueLabel?: string;
}

export function PnLChart({ data, height = 200, color = "#6366f1", valueLabel = "Value" }: PnLChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="flex h-[200px] items-center justify-center text-sm text-gray-600">
        No data available
      </div>
    );
  }

  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data}>
          <defs>
            <linearGradient id={`grad-${color.replace("#", "")}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={color} stopOpacity={0.25} />
              <stop offset="95%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" vertical={false} />
          <XAxis dataKey="time" stroke="#444" fontSize={10} tickLine={false} axisLine={false} />
          <YAxis stroke="#444" fontSize={10} tickLine={false} axisLine={false} tickFormatter={(v) => `$${v.toFixed(0)}`} />
          <Tooltip
            contentStyle={{ backgroundColor: "#000", border: "1px solid #222", borderRadius: "8px", fontSize: "12px" }}
            itemStyle={{ color: "#fff" }}
          />
          <Area type="monotone" dataKey="value" stroke={color} strokeWidth={2} fillOpacity={1} fill={`url(#grad-${color.replace("#", "")})`} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
