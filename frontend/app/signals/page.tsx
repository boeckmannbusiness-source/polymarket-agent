"use client";

import { useEffect, useState } from "react";
import { api, Signal } from "@/lib/api";
import { confidenceColor, timeAgo } from "@/lib/utils";

export default function SignalsPage() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    api.signals.list({ limit: 100, is_active: true }).then(setSignals).catch(console.error).finally(() => setLoading(false));
  }, []);

  const filtered = filter === "all" ? signals : signals.filter((s) => s.signal_type === filter);

  if (loading) return <div className="text-gray-500">Loading signals...</div>;

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-2xl font-bold text-white">Signals</h2>
        <div className="flex gap-2">
          {["all", "momentum", "whale_behavior", "anomaly", "sentiment"].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`rounded-full px-3 py-1 text-xs ${filter === f ? "bg-[var(--primary)] text-white" : "bg-[var(--card)] text-gray-400 hover:text-white"}`}
            >
              {f.replace("_", " ")}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        {filtered.map((s) => (
          <div key={s.id} className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <span className={`h-3 w-3 rounded-full ${confidenceColor(s.confidence)}`} />
                <div>
                  <div className="flex items-center gap-2">
                    <span className="rounded bg-[var(--background)] px-2 py-0.5 text-xs text-gray-400">
                      {s.signal_type.replace("_", " ")}
                    </span>
                    <span className={`text-sm font-medium uppercase ${s.direction === "bullish" ? "text-green-400" : s.direction === "bearish" ? "text-red-400" : "text-yellow-400"}`}>
                      {s.direction}
                    </span>
                  </div>
                  {s.reasoning && <p className="mt-1 text-sm text-gray-400">{s.reasoning}</p>}
                </div>
              </div>
              <div className="flex flex-col items-end gap-1">
                <span className="font-mono text-lg font-bold text-white">{(s.confidence * 100).toFixed(0)}%</span>
                <span className="text-xs text-gray-500">{timeAgo(s.generated_at)}</span>
              </div>
            </div>
            {s.source_agent && (
              <div className="mt-2 text-xs text-gray-600">Source: {s.source_agent}</div>
            )}
          </div>
        ))}
        {filtered.length === 0 && <div className="py-12 text-center text-gray-500">No signals found</div>}
      </div>
    </div>
  );
}
