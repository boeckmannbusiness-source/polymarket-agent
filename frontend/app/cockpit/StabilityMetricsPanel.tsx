"use client";

import { useMemo } from "react";
import type { CockpitOverview, CockpitInstability } from "@/lib/api";

function normalize(value: number, max: number): number {
  return Math.min(1, Math.max(0, value / max));
}

const TREND_META: Record<string, { arrow: string; color: string }> = {
  worsening: { arrow: "↑", color: "#FF1744" },
  improving: { arrow: "↓", color: "#00C853" },
  stable: { arrow: "→", color: "#888888" },
};

function GaugeBar({ score, color }: { score: number; color: string }) {
  const pct = (score * 100).toFixed(0);
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 rounded-full bg-[var(--border)] overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-xs font-mono text-gray-400 w-8 text-right">{pct}%</span>
    </div>
  );
}

export default function StabilityMetricsPanel({
  overview,
  instability,
}: {
  overview: CockpitOverview | null;
  instability: CockpitInstability | null;
}) {
  const forces = useMemo(() => {
    const sm = overview?.stability_metrics;
    const pl = overview?.pipeline;
    const ind = instability?.indicators;

    const pressure = ind
      ? Math.min(1,
          normalize(ind.flip_count, 10) * 0.3 +
          normalize(ind.chain_depth, 5) * 0.25 +
          normalize(ind.hysteresis_rejected, 20) * 0.2 +
          normalize(pl?.exposure_utilization_pct ?? 0, 100) * 0.25
        )
      : 0;

    const stability = instability
      ? 1 - instability.instability_score
      : 1;

    const throughput = pl
      ? normalize(pl.signal_rate_per_minute ?? 0, 200) * 0.5 +
        (pl.execution_success_rate ?? 1) * 0.5
      : 0.5;

    return { pressure, stability, throughput };
  }, [overview, instability]);

  const trendArrow = instability ? TREND_META[instability.trend] : TREND_META.stable;

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] px-5 py-4">
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">System Forces</span>
        <span className="text-[10px] text-gray-600">3 macro signals</span>
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-400 font-medium">Pressure</span>
            <span className="text-xs text-gray-500">load · backlog · memory</span>
          </div>
          <GaugeBar score={forces.pressure} color="#FF9800" />
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-400 font-medium">Stability</span>
            <span className="text-xs text-gray-500">flips · hysteresis · osc</span>
          </div>
          <GaugeBar score={forces.stability} color={forces.stability > 0.6 ? "#00C853" : forces.stability > 0.3 ? "#FFD600" : "#FF1744"} />
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1 text-xs text-gray-400 font-medium">
              Throughput
              <span className="font-mono text-[10px]" style={{ color: trendArrow.color }}>{trendArrow.arrow}</span>
            </span>
            <span className="text-xs text-gray-500">signals · executions</span>
          </div>
          <GaugeBar score={forces.throughput} color="#0066FF" />
        </div>
      </div>
    </div>
  );
}
