"use client";

import type { CockpitOverview, CockpitInstability, CockpitExplanation } from "@/lib/api";
import { MODE_COLORS } from "@/lib/utils";
import { Lock, Activity, TrendingUp, TrendingDown, Minus, AlertCircle, Info } from "lucide-react";

const STATE_META = {
  stable: { color: "#00C853", icon: Activity },
  watch: { color: "#FFD600", icon: Info },
  unstable: { color: "#FF1744", icon: AlertCircle },
};

const TREND_META = {
  worsening: { arrow: TrendingUp, color: "#FF1744" },
  improving: { arrow: TrendingDown, color: "#00C853" },
  stable: { arrow: Minus, color: "#888888" },
};

function riskBand(score: number): { label: string; color: string } {
  if (score <= 0.2) return { label: "LOW", color: "#00C853" };
  if (score <= 0.5) return { label: "MED", color: "#FFD600" };
  return { label: "HIGH", color: "#FF1744" };
}

export default function SystemHealthHeader({
  overview,
  instability,
  explanation,
}: {
  overview: CockpitOverview | null;
  instability: CockpitInstability | null;
  explanation: CockpitExplanation | null;
}) {
  const mode = overview?.current_mode;
  const modeName = mode?.mode.replace(/_/g, " ").toUpperCase() || "—";
  const modeColor = MODE_COLORS[mode?.mode || ""] || "#888";

  const state = (instability?.state || "stable") as keyof typeof STATE_META;
  const stateMeta = STATE_META[state];
  const StateIcon = stateMeta.icon;

  const trend = (instability?.trend || "stable") as keyof typeof TREND_META;
  const trendMeta = TREND_META[trend];
  const TrendIcon = trendMeta.arrow;

  const risk = riskBand(instability?.instability_score ?? 0);

  const isManual = mode?.is_manual_override;
  const ttl = mode?.ttl_seconds;

  const cause = explanation?.primary_driver || instability?.primary_drivers[0] || "No anomalies detected";

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] px-5 py-4 space-y-3 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-6">
          {/* Mode Segment */}
          <div className="flex items-center gap-3">
            <div
              className="h-3 w-3 rounded-full animate-pulse"
              style={{ backgroundColor: modeColor, boxShadow: `0 0 8px ${modeColor}80` }}
            />
            <div className="flex flex-col">
              <span className="text-[10px] text-gray-500 font-bold uppercase tracking-widest">Operation Mode</span>
              <span className="text-sm font-bold text-white tracking-wider">{modeName}</span>
            </div>
          </div>

          <div className="h-8 w-px bg-[var(--border)] hidden sm:block" />

          {/* Stability Segment */}
          <div className="flex items-center gap-3">
            <StateIcon className="h-4 w-4" style={{ color: stateMeta.color }} />
            <div className="flex flex-col">
              <span className="text-[10px] text-gray-500 font-bold uppercase tracking-widest">Stability</span>
              <span className="text-sm font-bold text-gray-200 capitalize">{state}</span>
            </div>
          </div>

          <div className="h-8 w-px bg-[var(--border)] hidden sm:block" />

          {/* Risk Segment */}
          <div className="flex items-center gap-3">
            <div className="h-4 w-4 rounded flex items-center justify-center bg-gray-800 border border-[var(--border)]">
               <div className="h-2 w-2 rounded-full" style={{ backgroundColor: risk.color }} />
            </div>
            <div className="flex flex-col">
              <span className="text-[10px] text-gray-500 font-bold uppercase tracking-widest">Risk Score</span>
              <span className="text-sm font-bold" style={{ color: risk.color }}>{risk.label} ({(instability?.instability_score ?? 0).toFixed(2)})</span>
            </div>
          </div>
        </div>

        {/* Right side: Trends & Overrides */}
        <div className="flex items-center gap-4">
          {isManual && (
            <div className="flex items-center gap-2 px-2 py-1 rounded bg-orange-500/10 border border-orange-500/30 text-orange-400">
              <Lock className="h-3.5 w-3.5" />
              <span className="text-[10px] font-bold uppercase">Manual Override</span>
              {ttl !== null && ttl !== undefined && (
                <span className="text-[10px] font-mono bg-orange-500/20 px-1 rounded">{ttl}s</span>
              )}
            </div>
          )}

          <div className="flex items-center gap-2 text-gray-400">
            <TrendIcon className="h-4 w-4" style={{ color: trendMeta.color }} />
            <span className="text-[10px] font-bold uppercase tracking-widest">{trend} trend</span>
          </div>
        </div>
      </div>

      {/* Narrative row */}
      <div className="pt-2 border-t border-[var(--border)] flex items-baseline gap-3">
        <span className="text-[10px] font-bold text-gray-600 uppercase tracking-widest shrink-0">Diagnosis:</span>
        <span className="text-xs text-gray-400 italic leading-relaxed">
          {explanation?.transition_summary || cause}
        </span>
      </div>
    </div>
  );
}
