"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { api, type CockpitOverview, type CockpitInstability, type CockpitExplanation } from "@/lib/api";
import SystemHealthHeader from "./SystemHealthHeader";
import SystemNarrative from "./SystemNarrative";
import PrimarySignal from "./PrimarySignal";
import DecisionBanner from "./DecisionBanner";
import StabilityMetricsPanel from "./StabilityMetricsPanel";
import ModeTimeline from "./ModeTimeline";
import StressSimulationPanel from "./StressSimulationPanel";
import { Activity, ChevronRight } from "lucide-react";

const POLL_INTERVAL = 5000;

export default function CockpitPage() {
  const [overview, setOverview] = useState<CockpitOverview | null>(null);
  const [instability, setInstability] = useState<CockpitInstability | null>(null);
  const [explanation, setExplanation] = useState<CockpitExplanation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchAll = useCallback(async () => {
    try {
      const [ov, inst, expl] = await Promise.all([
        api.cockpit.overview(),
        api.cockpit.instability(30),
        api.cockpit.explanation(),
      ]);
      setOverview(ov);
      setInstability(inst);
      setExplanation(expl);
      setError(null);
    } catch (e) {
      console.error("Cockpit poll error", e);
      setError("Connection lost — retrying...");
    }
  }, []);

  useEffect(() => {
    fetchAll();
    if (!paused) {
      intervalRef.current = setInterval(fetchAll, POLL_INTERVAL);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchAll, paused]);

  return (
    <div className="space-y-3">
      {/* Top bar: title + controls */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-white">System Stability Cockpit</h2>
        <div className="flex items-center gap-3">
          {error && <span className="text-xs text-red-400">{error}</span>}
          <button
            onClick={() => setPaused(!paused)}
            className="flex items-center gap-1.5 rounded border border-[var(--border)] bg-[var(--card)] px-2 py-1 text-xs text-gray-400 hover:text-white transition-colors"
          >
            <Activity className="h-3 w-3" />
            {paused ? "Resume" : "Pause"}
          </button>
          <span className={`text-[10px] ${paused ? "text-yellow-400" : "text-green-400"}`}>
            {paused ? "PAUSED" : `${POLL_INTERVAL / 1000}s polling`}
          </span>
        </div>
      </div>

      {/* 1. SYSTEM HEALTH HEADER — single source of truth */}
      <SystemHealthHeader overview={overview} instability={instability} explanation={explanation} />

      {/* 2. SYSTEM NARRATIVE — one sentence */}
      <SystemNarrative text={explanation?.transition_summary ?? null} />

      {/* 3. PRIMARY SIGNAL — diagnosis, not analytics */}
      <PrimarySignal data={instability} />

      {/* 4. DECISION BANNER — action guidance */}
      <DecisionBanner data={instability} />

      {/* 5. SYSTEM FORCES — collapsed macro signals */}
      <details className="group">
        <summary className="flex cursor-pointer items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--card)] px-4 py-2.5 text-sm text-gray-400 hover:text-white transition-colors [&::-webkit-details-marker]:hidden">
          <ChevronRight className="h-3.5 w-3.5 text-gray-600 group-open:rotate-90 transition-transform" />
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">System Forces</span>
          <span className="text-[10px] text-gray-600">— 3 macro signals (pressure, stability, throughput)</span>
        </summary>
        <div className="mt-2">
          <StabilityMetricsPanel overview={overview} instability={instability} />
        </div>
      </details>

      {/* 6. MODE TIMELINE — collapsed, for incident review */}
      <details className="group">
        <summary className="flex cursor-pointer items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--card)] px-4 py-2.5 text-sm text-gray-400 hover:text-white transition-colors [&::-webkit-details-marker]:hidden">
          <ChevronRight className="h-3.5 w-3.5 text-gray-600 group-open:rotate-90 transition-transform" />
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Mode Timeline</span>
          <span className="text-[10px] text-gray-600">— transition history for incident review</span>
        </summary>
        <div className="mt-2">
          <ModeTimeline data={overview?.recent_transitions ?? null} />
        </div>
      </details>

      {/* 7. INCIDENT LAB — hidden simulation */}
      <details className="group">
        <summary className="flex cursor-pointer items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--card)] px-4 py-2.5 text-sm text-gray-400 hover:text-white transition-colors [&::-webkit-details-marker]:hidden">
          <ChevronRight className="h-3.5 w-3.5 text-gray-600 group-open:rotate-90 transition-transform" />
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Incident Lab</span>
          <span className="text-[10px] text-gray-600">— stress simulation & what-if analysis</span>
        </summary>
        <div className="mt-2">
          <StressSimulationPanel />
        </div>
      </details>
    </div>
  );
}
