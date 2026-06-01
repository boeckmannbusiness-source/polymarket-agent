"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { api, type CockpitOverview, type CockpitInstability, type CockpitExplanation } from "@/lib/api";
import SystemHealthHeader from "./SystemHealthHeader";
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
    <div className="space-y-4 max-w-7xl mx-auto pb-10">
      {/* Top bar: title + controls */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-white tracking-tight">System Stability Cockpit</h2>
        <div className="flex items-center gap-3">
          {error && <span className="text-xs text-red-400 animate-pulse">{error}</span>}
          <button
            onClick={() => setPaused(!paused)}
            className="flex items-center gap-1.5 rounded border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-xs text-gray-400 hover:text-white transition-all hover:bg-[var(--border)]"
          >
            <Activity className={`h-3 w-3 ${paused ? "" : "animate-pulse"}`} />
            {paused ? "Resume" : "Pause"}
          </button>
          <span className={`text-[10px] font-mono font-bold tracking-widest ${paused ? "text-yellow-500" : "text-green-500"}`}>
            {paused ? "PAUSED" : "LIVE"}
          </span>
        </div>
      </div>

      {/* 1. SYSTEM HEALTH HEADER — single source of truth */}
      <SystemHealthHeader overview={overview} instability={instability} explanation={explanation} />

      {/* 2. DECISION BANNER — action guidance */}
      <DecisionBanner data={instability} />

      <div className="grid grid-cols-1 gap-4 pt-4">
        {/* 3. SYSTEM FORCES — collapsed macro signals */}
        <details className="group" open>
          <summary className="flex cursor-pointer items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--card)] px-4 py-3 text-sm text-gray-400 hover:text-white transition-colors [&::-webkit-details-marker]:hidden">
            <div className="flex items-center gap-2">
              <ChevronRight className="h-4 w-4 text-gray-600 group-open:rotate-90 transition-transform" />
              <span className="text-xs font-bold text-gray-500 uppercase tracking-widest">System Forces</span>
            </div>
            <span className="text-[10px] text-gray-600 font-medium">Pressure · Stability · Throughput</span>
          </summary>
          <div className="mt-3">
            <StabilityMetricsPanel overview={overview} instability={instability} />
          </div>
        </details>

        {/* 4. MODE TIMELINE — collapsed, for incident review */}
        <details className="group">
          <summary className="flex cursor-pointer items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--card)] px-4 py-3 text-sm text-gray-400 hover:text-white transition-colors [&::-webkit-details-marker]:hidden">
             <div className="flex items-center gap-2">
              <ChevronRight className="h-4 w-4 text-gray-600 group-open:rotate-90 transition-transform" />
              <span className="text-xs font-bold text-gray-500 uppercase tracking-widest">Transition History</span>
            </div>
            <span className="text-[10px] text-gray-600 font-medium">Mode shift audit log</span>
          </summary>
          <div className="mt-3">
            <ModeTimeline data={overview?.recent_transitions ?? null} />
          </div>
        </details>

        {/* 5. INCIDENT LAB — hidden simulation */}
        <details className="group">
          <summary className="flex cursor-pointer items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--card)] px-4 py-3 text-sm text-gray-400 hover:text-white transition-colors [&::-webkit-details-marker]:hidden">
            <div className="flex items-center gap-2">
              <ChevronRight className="h-4 w-4 text-gray-600 group-open:rotate-90 transition-transform" />
              <span className="text-xs font-bold text-gray-500 uppercase tracking-widest">Incident Lab</span>
            </div>
            <span className="text-[10px] text-gray-600 font-medium">Stress simulation & what-if</span>
          </summary>
          <div className="mt-3">
            <StressSimulationPanel />
          </div>
        </details>
      </div>
    </div>
  );
}
