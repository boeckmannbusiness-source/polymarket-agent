"use client";

import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";

interface DrawdownChartProps {
  data: { time: string; drawdown: number }[];
  height?: number;
}

export function DrawdownChart({ data, height = 100 }: DrawdownChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="flex h-[100px] items-center justify-center text-sm text-gray-600">
        No drawdown data
      </div>
    );
  }

  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data}>
          <defs>
            <linearGradient id="dd-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#f43f5e" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" vertical={false} />
          <XAxis dataKey="time" stroke="#444" fontSize={9} tickLine={false} axisLine={false} />
          <YAxis stroke="#444" fontSize={9} tickLine={false} axisLine={false} tickFormatter={(v) => `${(v * 100).toFixed(1)}%`} />
          <Tooltip
            contentStyle={{ backgroundColor: "#000", border: "1px solid #222", borderRadius: "8px", fontSize: "12px" }}
            formatter={(value: number) => [`${(value * 100).toFixed(2)}%`, "Drawdown"]}
          />
          <Area type="monotone" dataKey="drawdown" stroke="#f43f5e" strokeWidth={1.5} fillOpacity={1} fill="url(#dd-grad)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
