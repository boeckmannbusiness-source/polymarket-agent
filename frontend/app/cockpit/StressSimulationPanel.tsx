"use client";

import { useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { SimulationSummary } from "@/lib/api";
import { MODE_COLORS } from "@/lib/utils";
import { api } from "@/lib/api";
import {
  Zap,
  Waves,
  Thermometer,
  Grid3X3,
  Loader2,
} from "lucide-react";

const SCENARIOS = [
  { label: "Spike Shock", cycles: 1, seed: 42, icon: Zap, color: "#FF9800" },
  { label: "Oscillation Load", cycles: 8, seed: 42, icon: Waves, color: "#FFD600" },
  { label: "Slow Burn", cycles: 15, seed: 42, icon: Thermometer, color: "#FF1744" },
  { label: "Full Stress Matrix", cycles: 24, seed: 42, icon: Grid3X3, color: "#9C27B0" },
];

function ResultCard({ result }: { result: SimulationSummary }) {
  const stabilityScore = Math.max(0, 100 - result.flip_count * 12 - result.oscillation_events * 15);
  const scoreColor = stabilityScore >= 70 ? "#00C853" : stabilityScore >= 40 ? "#FFD600" : "#FF1744";

  return (
    <div className="mt-3 rounded border border-[var(--border)] bg-[var(--background)] p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Simulation Results</span>
        <Badge variant="outline" className="text-[10px]">
          {result.total_duration_s.toFixed(0)}s simulated
        </Badge>
      </div>

      <div className="flex items-center gap-3 mb-3">
        <span
          className="flex h-10 w-10 items-center justify-center rounded-full text-sm font-bold"
          style={{
            backgroundColor: scoreColor + "20",
            border: `2px solid ${scoreColor}`,
            color: scoreColor,
          }}
        >
          {stabilityScore}
        </span>
        <div>
          <div className="text-xs text-gray-400">Stability Score</div>
          <div className="text-lg font-bold text-white">{result.flip_count} flips</div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 text-xs">
        <div>
          <span className="text-gray-500">Transitions</span>
          <div className="text-white font-semibold">{result.transitions}</div>
        </div>
        <div>
          <span className="text-gray-500">Max Chain</span>
          <div className="text-white font-semibold">{result.max_escalation_chain}</div>
        </div>
        <div>
          <span className="text-gray-500">Oscillations</span>
          <div className="text-white font-semibold">{result.oscillation_events}</div>
        </div>
        <div>
          <span className="text-gray-500">Rejected (hyst)</span>
          <div className="text-white font-semibold">{result.rejected_by_hysteresis}</div>
        </div>
        <div>
          <span className="text-gray-500">Rejected (hold)</span>
          <div className="text-white font-semibold">{result.rejected_by_hold}</div>
        </div>
        <div>
          <span className="text-gray-500">Proposed/Blocked</span>
          <div className="text-white font-semibold">{result.mode_proposed_but_rejected}</div>
        </div>
      </div>

      {result.time_in_mode_pct && Object.keys(result.time_in_mode_pct).length > 0 && (
        <div className="mt-2">
          <span className="text-[10px] text-gray-500 uppercase tracking-wider">Mode Distribution</span>
          <div className="mt-1 flex h-2 w-full overflow-hidden rounded-full bg-[var(--border)]">
            {Object.entries(result.time_in_mode_pct).map(([mode, pct]) => (
              <div
                key={mode}
                style={{
                  width: `${pct}%`,
                  backgroundColor: MODE_COLORS[mode] || "#888",
                  opacity: 0.7,
                }}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function StressSimulationPanel() {
  const [loading, setLoading] = useState<string | null>(null);
  const [results, setResults] = useState<{ scenario: string; data: SimulationSummary }[]>([]);

  const runScenario = async (label: string, cycles: number, seed: number) => {
    setLoading(label);
    try {
      const data = await api.debug.simulate(cycles, seed);
      setResults((prev) => [{ scenario: label, data }, ...prev.filter((r) => r.scenario !== label)].slice(0, 4));
    } catch (e) {
      console.error("Simulation failed", e);
    } finally {
      setLoading(null);
    }
  };

  const runAll = async () => {
    for (const s of SCENARIOS) {
      await runScenario(s.label, s.cycles, s.seed);
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Stress Simulation</CardTitle>
          <Button variant="destructive" size="sm" onClick={runAll} disabled={loading !== null}>
            {loading ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : null}
            Run Full Matrix
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-2">
          {SCENARIOS.map((s) => {
            const Icon = s.icon;
            const isRunning = loading === s.label;
            return (
              <Button
                key={s.label}
                variant="outline"
                size="sm"
                onClick={() => runScenario(s.label, s.cycles, s.seed)}
                disabled={loading !== null}
                style={{ borderColor: s.color + "40", color: s.color }}
              >
                {isRunning ? (
                  <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                ) : (
                  <Icon className="mr-1 h-3 w-3" />
                )}
                {s.label}
              </Button>
            );
          })}
        </div>

        <div className="mt-2 space-y-1">
          {results.map((r) => (
            <ResultCard key={r.scenario} result={r.data} />
          ))}
          {results.length === 0 && (
            <div className="mt-3 text-center text-xs text-gray-600">
              Run a simulation to see results
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
