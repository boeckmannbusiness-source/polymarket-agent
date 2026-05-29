"use client";

import type { CockpitInstability } from "@/lib/api";

function recommendation(data: CockpitInstability): { text: string; color: string; icon: string } {
  const { state, trend, indicators, instability_score } = data;

  if (state === "unstable") {
    if (indicators.oscillation_detected) {
      return { text: "System oscillation detected — consider throttling execution", color: "#FF1744", icon: "⚠" };
    }
    return { text: "System entering protective mode — review pipeline health", color: "#FF1744", icon: "⚠" };
  }

  if (state === "watch") {
    if (indicators.flip_count > 3) {
      return { text: "Reduce execution throughput — mode flips are elevated", color: "#FFD600", icon: "→" };
    }
    if (trend === "worsening") {
      return { text: "Monitor backlog — no intervention required yet", color: "#FFD600", icon: "→" };
    }
    return { text: "Observe system — degradation may self-correct", color: "#FFD600", icon: "→" };
  }

  if (instability_score < 0.05) {
    return { text: "No intervention required — system nominal", color: "#00C853", icon: "✓" };
  }
  return { text: "No intervention required", color: "#00C853", icon: "✓" };
}

export default function DecisionBanner({ data }: { data: CockpitInstability | null }) {
  if (!data) return null;

  const rec = recommendation(data);

  return (
    <div
      className="rounded-lg border px-5 py-3 flex items-center gap-3"
      style={{
        borderColor: rec.color + "30",
        backgroundColor: rec.color + "08",
      }}
    >
      <span className="text-base" style={{ color: rec.color }}>{rec.icon}</span>
      <span className="text-sm font-medium" style={{ color: rec.color }}>
        ACTION RECOMMENDATION
      </span>
      <span className="text-sm text-gray-300">{rec.text}</span>
    </div>
  );
}
