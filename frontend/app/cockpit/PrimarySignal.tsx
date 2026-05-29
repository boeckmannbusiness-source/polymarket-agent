"use client";

import type { CockpitInstability } from "@/lib/api";

const STATE_META = {
  stable: { color: "#00C853", label: "STABLE", bg: "bg-green-500/10", border: "border-green-500/30" },
  watch: { color: "#FFD600", label: "WATCH", bg: "bg-yellow-500/10", border: "border-yellow-500/30" },
  unstable: { color: "#FF1744", label: "UNSTABLE", bg: "bg-red-500/10", border: "border-red-500/30" },
};

function topIndicator(data: CockpitInstability): { label: string; value: string } | null {
  const ind = data.indicators;
  if (ind.oscillation_detected) return { label: "oscillation events", value: String(ind.oscillation_events) };
  if (ind.flip_count > 0) return { label: "mode flips", value: String(ind.flip_count) };
  if (ind.chain_depth > 0) return { label: "escalation chain", value: String(ind.chain_depth) };
  if (ind.hysteresis_rejected > 0) return { label: "hysteresis rejections", value: String(ind.hysteresis_rejected) };
  return null;
}

export default function PrimarySignal({ data }: { data: CockpitInstability | null }) {
  if (!data) return null;

  const meta = STATE_META[data.state] || STATE_META.stable;
  const cause = data.primary_drivers[0] || data.status_message;
  const top = topIndicator(data);

  return (
    <div className={`rounded-lg border ${meta.bg} ${meta.border} px-5 py-4`}>
      <div className="flex flex-wrap items-start gap-4">
        {/* State badge */}
        <div className="flex items-center gap-2 shrink-0">
          <span className="h-3 w-3 rounded-full" style={{ backgroundColor: meta.color }} />
          <span className="text-sm font-bold tracking-wider" style={{ color: meta.color }}>
            {meta.label}
          </span>
        </div>

        {/* Cause + primary metric */}
        <div className="flex-1 min-w-0">
          <p className="text-sm text-gray-200">{cause}</p>
          {top && (
            <p className="mt-1 text-xs text-gray-500">
              Primary signal: {top.label} ({top.value})
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
