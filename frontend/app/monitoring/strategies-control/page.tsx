"use client";

import { useState, useEffect, useCallback } from "react";
import { ControlSwitch } from "@/components/ControlSwitch";
import { CircuitBreakerBadge } from "@/components/CircuitBreakerBadge";
import { RiskGauge } from "@/components/RiskGauge";
import { LiveIndicator } from "@/components/LiveIndicator";
import { api } from "@/lib/api";

export default function StrategiesControlPage() {
  const [strategies, setStrategies] = useState<any[]>([]);
  const [paused, setPaused] = useState<string[]>([]);
  const [breakers, setBreakers] = useState<any[]>([]);
  const [tradingEnabled, setTradingEnabled] = useState(true);
  const [loading, setLoading] = useState(true);

  const fetchState = useCallback(async () => {
    try {
      const [control, pausedList, breakerData] = await Promise.all([
        fetch("/api/v1/control/state").then(r => r.json()),
        fetch("/api/v1/control/strategies/paused").then(r => r.json()),
        fetch("/api/v1/incidents/breakers/active").then(r => r.json()),
      ]);
      setTradingEnabled(control.trading_enabled);
      setPaused(pausedList.paused || []);
      setBreakers(breakerData.breakers || []);

      if (strategies.length === 0) {
        const stratData = await api.portfolio.strategies();
        setStrategies(stratData || []);
      }
    } catch {
    } finally {
      setLoading(false);
    }
  }, [strategies.length]);

  useEffect(() => { fetchState(); }, [fetchState]);

  const handleToggleTrading = async (enabled: boolean) => {
    await fetch(enabled ? "/api/v1/control/trading/enable" : "/api/v1/control/trading/disable", { method: "POST" });
    setTradingEnabled(enabled);
  };

  const handleToggleStrategy = async (agentId: string, isPaused: boolean) => {
    await fetch(
      isPaused
        ? `/api/v1/control/strategy/${agentId}/resume`
        : `/api/v1/control/strategy/${agentId}/pause`,
      { method: "POST" },
    );
    setPaused((prev) =>
      isPaused ? prev.filter((id) => id !== agentId) : [...prev, agentId],
    );
  };

  const handleResetBreaker = async (name: string) => {
    await fetch(`/api/v1/incidents/breakers/reset/${name}`, { method: "POST" });
    fetchState();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Strategy Control</h1>
          <p className="text-[10px] text-gray-500 uppercase tracking-wider">Live ops control panel</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3">
            Global Control
          </h2>
          <ControlSwitch
            label="Trading Enabled"
            initialState={tradingEnabled}
            onChange={handleToggleTrading}
          />
          <div className="mt-3 text-xs text-muted-foreground">
            Status: {tradingEnabled ? (
              <span className="text-emerald-400">Enabled</span>
            ) : (
              <span className="text-red-400">Disabled</span>
            )}
          </div>
        </div>

        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3">
            System Health
          </h2>
          <RiskGauge score={tradingEnabled ? 85 : 30} label="Health Score" />
        </div>

        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3">
            Circuit Breakers
          </h2>
          <div className="space-y-2">
            {["loss_circuit", "execution_failure", "latency_spike", "drift_breaker"].map((name) => {
              const active = breakers.find((b: any) => b.name === name);
              return (
                <CircuitBreakerBadge
                  key={name}
                  name={name}
                  triggered={!!active}
                  reason={active?.reason}
                  onClick={() => active && handleResetBreaker(name)}
                />
              );
            })}
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
          Strategies ({strategies.length})
        </h2>
        {loading && (
          <div className="text-center py-8 text-xs text-muted-foreground">Loading strategies...</div>
        )}
        {!loading && strategies.length === 0 && (
          <div className="text-center py-8 text-xs text-muted-foreground">No strategies found</div>
        )}
        <div className="space-y-2">
          {strategies.map((s: any) => {
            const isPaused = paused.includes(s.agent_id || s.name);
            return (
              <div key={s.agent_id || s.name} className="flex items-center justify-between py-2 px-3 border border-border rounded-lg">
                <div>
                  <span className="text-sm font-medium text-white">{s.agent_id || s.name}</span>
                  <div className="flex items-center gap-3 mt-1 text-[10px] text-muted-foreground">
                    <span>{s.total_trades || 0} trades</span>
                    <span>{(s.win_rate || 0).toFixed(0)}% WR</span>
                    <span className={s.total_pnl >= 0 ? "text-emerald-500" : "text-red-500"}>
                      PnL: ${(s.total_pnl || 0).toFixed(2)}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] ${isPaused ? "text-amber-400" : "text-emerald-400"}`}>
                    {isPaused ? "Paused" : "Active"}
                  </span>
                  <button
                    onClick={() => handleToggleStrategy(s.agent_id || s.name, isPaused)}
                    className={`px-2 py-1 text-[10px] border rounded ${
                      isPaused
                        ? "border-emerald-700 text-emerald-400 hover:bg-emerald-950"
                        : "border-amber-700 text-amber-400 hover:bg-amber-950"
                    }`}
                  >
                    {isPaused ? "Resume" : "Pause"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
