"use client";

import type { CockpitOverview, CockpitInstability, CockpitExplanation } from "@/lib/api";
import { MODE_COLORS } from "@/lib/utils";

const STATE_META = {
  stable: { color: "#00C853" },
  watch: { color: "#FFD600" },
  unstable: { color: "#FF1744" },
};

const TREND_META = {
  worsening: { arrow: "↑", color: "#FF1744" },
  improving: { arrow: "↓", color: "#00C853" },
  stable: { arrow: "→", color: "#888888" },
};

function riskBand(score: number): { label: string; color: string } {
  if (score <= 0.2) return { label: "low", color: "#00C853" };
  if (score <= 0.5) return { label: "medium", color: "#FFD600" };
  return { label: "high", color: "#FF1744" };
}

function actionLabel(state: string, risk: string, trend: string): { action: string; color: string } {
  if (state === "unstable" || risk === "high") return { action: "intervene", color: "#FF1744" };
  if (state === "watch" || trend === "worsening") return { action: "monitor", color: "#FFD600" };
  return { action: "none", color: "#00C853" };
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
  const trend = (instability?.trend || "stable") as keyof typeof TREND_META;
  const trendMeta = TREND_META[trend];
  const risk = riskBand(instability?.instability_score ?? 0);
  const act = actionLabel(state, risk.label, trend);

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] px-5 py-4">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
        {/* Mode */}
        <div className="flex items-center gap-2">
          <span className="h-3 w-3 rounded-full" style={{ backgroundColor: modeColor }} />
          <span className="text-sm font-bold text-white tracking-wider">{modeName}</span>
        </div>

        <div className="h-4 w-px bg-[var(--border)]" />

        {/* Stability state */}
        <div className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: stateMeta.color }} />
          <span className="text-sm text-gray-300 font-medium capitalize">{state}</span>
        </div>

        <div className="h-4 w-px bg-[var(--border)]" />

        {/* Trend */}
        <div className="flex items-center gap-1">
          <span className="text-sm font-mono" style={{ color: trendMeta.color }}>{trendMeta.arrow}</span>
          <span className="text-sm text-gray-400">{trend}</span>
        </div>

        <div className="h-4 w-px bg-[var(--border)]" />

        {/* Risk band */}
        <div className="flex items-center gap-1.5">
          <span
            className="inline-block h-2 w-6 rounded-full"
            style={{ backgroundColor: risk.color }}
          />
          <span className="text-sm" style={{ color: risk.color }}>
            RISK: {risk.label}
          </span>
        </div>

        <div className="h-4 w-px bg-[var(--border)]" />

        {/* Action */}
        <div className="flex items-center gap-1.5">
          <span className="text-sm font-semibold" style={{ color: act.color }}>
            ACTION: {act.action}
          </span>
        </div>

        {/* Narrative summary (compact) */}
        {explanation?.transition_summary && (
          <>
            <div className="h-4 w-px bg-[var(--border)]" />
            <span className="text-xs text-gray-500 truncate max-w-md" title={explanation.transition_summary}>
              {explanation.transition_summary}
            </span>
          </>
        )}
      </div>
    </div>
  );
}
