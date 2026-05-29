"use client";

import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import type { CockpitInstability } from "@/lib/api";

const STATE_META = {
  stable: {
    color: "#00C853",
    bg: "bg-green-500/10",
    border: "border-green-500/30",
    label: "STABLE",
    pulse: false,
  },
  watch: {
    color: "#FFD600",
    bg: "bg-yellow-500/10",
    border: "border-yellow-500/30",
    label: "WATCH",
    pulse: true,
  },
  unstable: {
    color: "#FF1744",
    bg: "bg-red-500/10",
    border: "border-red-500/30",
    label: "UNSTABLE",
    pulse: true,
  },
};

export default function InstabilityIndicator({ data }: { data: CockpitInstability | null }) {
  if (!data) {
    return (
      <Card>
        <CardHeader><CardTitle>System Health</CardTitle></CardHeader>
        <CardContent><div className="text-sm text-gray-500">Loading...</div></CardContent>
      </Card>
    );
  }

  const meta = STATE_META[data.state] || STATE_META.stable;
  const scorePct = (data.instability_score * 100).toFixed(0);
  const trendIcon = data.trend === "worsening" ? "↑" : data.trend === "improving" ? "↓" : "→";

  return (
    <Card className={`${meta.bg} ${meta.border}`}>
      <CardHeader>
        <CardTitle>System Health</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col items-center gap-3">
          <div className="relative flex items-center justify-center">
            <span
              className="h-16 w-16 rounded-full flex items-center justify-center text-sm font-bold"
              style={{
                backgroundColor: meta.color + "20",
                border: `3px solid ${meta.color}`,
                color: meta.color,
              }}
            >
              {scorePct}%
            </span>
            {meta.pulse && (
              <span
                className="absolute h-16 w-16 rounded-full animate-ping opacity-30"
                style={{ backgroundColor: meta.color }}
              />
            )}
          </div>

          <span className="text-lg font-bold tracking-wider" style={{ color: meta.color }}>
            {meta.label}
          </span>

          <span className="text-sm text-gray-300 text-center">{data.status_message}</span>

          {data.primary_drivers.length > 0 && (
            <div className="w-full space-y-1 mt-1">
              <span className="text-xs text-gray-500 uppercase tracking-wider">Drivers</span>
              {data.primary_drivers.map((d, i) => (
                <div key={i} className="flex items-center gap-1.5 text-xs text-gray-400">
                  <span className="h-1 w-1 rounded-full bg-gray-500" />
                  {d}
                </div>
              ))}
            </div>
          )}

          <div className="flex items-center gap-2 text-xs text-gray-500 mt-1">
            <span>Trend: {trendIcon}</span>
            <span className="text-gray-600">|</span>
            <span>Score: {data.instability_score.toFixed(3)}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
