"use client";

import { useMemo } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ReferenceArea,
} from "recharts";
import { MODE_COLORS, MODE_INDICES } from "@/lib/utils";
import type { TransitionRecord } from "@/lib/api";

function modeVariant(mode: string): any {
  const map: Record<string, any> = {
    normal: "mode_normal",
    degraded: "mode_degraded",
    protected: "mode_protected",
    read_only: "mode_read_only",
    emergency_stop: "mode_emergency_stop",
  };
  return map[mode] || "default";
}

const MODE_NAMES: Record<number, string> = {
  0: "NORMAL",
  1: "DEGRADED",
  2: "PROTECTED",
  3: "READ_ONLY",
  4: "EMERGENCY_STOP",
};

interface TimelinePoint {
  time: number;
  modeIndex: number;
  modeName: string;
  label: string;
}

function buildTimeline(transitions: TransitionRecord[]): TimelinePoint[] {
  if (!transitions || transitions.length === 0) return [];
  const reversed = [...transitions].reverse();
  const points: TimelinePoint[] = [];
  const start = reversed[0];
  points.push({
    time: 0,
    modeIndex: MODE_INDICES[start.from_mode] ?? 0,
    modeName: start.from_mode,
    label: start.created_at
      ? new Date(start.created_at).toLocaleTimeString()
      : "0",
  });
  reversed.forEach((t, i) => {
    const idx = MODE_INDICES[t.to_mode] ?? 0;
    points.push({
      time: (i + 1) * 1,
      modeIndex: idx,
      modeName: t.to_mode,
      label: t.created_at
        ? new Date(t.created_at).toLocaleTimeString()
        : `${i + 1}`,
    });
  });
  return points;
}

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-xs shadow-lg">
      <div className="font-semibold text-white">{p.modeName.toUpperCase()}</div>
      <div className="text-gray-400">{MODE_NAMES[p.modeIndex] || "UNKNOWN"}</div>
      <div className="text-gray-500">{p.label}</div>
    </div>
  );
}

export default function ModeTimeline({ data }: { data: TransitionRecord[] | null }) {
  const timeline = useMemo(() => buildTimeline(data || []), [data]);
  const latest = data && data.length > 0 ? data[0] : null;
  const transitionCount = data?.length || 0;

  const modeColors = Object.values(MODE_COLORS);
  const zones = [
    { y1: -0.5, y2: 0.5, fill: MODE_COLORS.normal + "10" },
    { y1: 0.5, y2: 1.5, fill: MODE_COLORS.degraded + "10" },
    { y1: 1.5, y2: 2.5, fill: MODE_COLORS.protected + "10" },
    { y1: 2.5, y2: 3.5, fill: MODE_COLORS.read_only + "10" },
    { y1: 3.5, y2: 4.5, fill: MODE_COLORS.emergency_stop + "10" },
  ];

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Mode Timeline</CardTitle>
          <div className="flex items-center gap-3">
            {Object.entries(MODE_COLORS).map(([mode, color]) => (
              <div key={mode} className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
                <span className="text-[10px] text-gray-500 capitalize">{mode.replace(/_/g, " ")}</span>
              </div>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {latest && (
          <div className="mb-3 flex items-center gap-2">
            <Badge variant={modeVariant(latest.to_mode)} className="text-xs">
              {latest.to_mode.toUpperCase()}
            </Badge>
            <span className="text-xs text-gray-500">
              {latest.from_mode.toUpperCase()} → {latest.to_mode.toUpperCase()}
            </span>
            <span className="text-xs text-gray-600">
              {latest.created_at ? new Date(latest.created_at).toLocaleTimeString() : ""}
            </span>
            <span className="text-xs text-gray-600 ml-auto">{transitionCount} transitions shown</span>
          </div>
        )}

        {timeline.length > 1 ? (
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={timeline} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis
                  dataKey="time"
                  tick={{ fontSize: 10, fill: "#888" }}
                  axisLine={{ stroke: "var(--border)" }}
                  tickLine={false}
                  label={{ value: "Transitions", position: "insideBottom", offset: -5, style: { fill: "#888", fontSize: 10 } }}
                />
                <YAxis
                  domain={[-0.5, 4.5]}
                  ticks={[0, 1, 2, 3, 4]}
                  tickFormatter={(v) => MODE_NAMES[v] || ""}
                  tick={{ fontSize: 9, fill: "#888" }}
                  axisLine={{ stroke: "var(--border)" }}
                  tickLine={false}
                  width={70}
                />
                {zones.map((z, i) => (
                  <ReferenceArea key={i} y1={z.y1} y2={z.y2} fill={z.fill} strokeWidth={0} />
                ))}
                {[0, 1, 2, 3, 4].map((v) => (
                  <ReferenceLine
                    key={v}
                    y={v}
                    stroke="var(--border)"
                    strokeDasharray="2 2"
                    strokeWidth={0.5}
                  />
                ))}
                <Tooltip content={<CustomTooltip />} />
                <Line
                  type="stepAfter"
                  dataKey="modeIndex"
                  stroke="var(--primary)"
                  strokeWidth={2}
                  dot={(props: any) => {
                    const color = MODE_COLORS[props.payload.modeName] || "#888";
                    return (
                      <circle
                        key={props.key}
                        cx={props.cx}
                        cy={props.cy}
                        r={4}
                        fill={color}
                        stroke="#0A0B0D"
                        strokeWidth={2}
                      />
                    );
                  }}
                  activeDot={{ r: 6, fill: "var(--primary)" }}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="flex h-48 items-center justify-center text-sm text-gray-500">
            {data === null ? "Loading..." : "No transitions recorded yet"}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
