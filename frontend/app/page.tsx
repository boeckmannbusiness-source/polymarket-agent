"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import {
  usePortfolioSnapshot, usePortfolioHistory, useMarketExposure,
  usePositions,
} from "@/lib/hooks";
import { StatCard } from "@/components/StatCard";
import { PnLChart } from "@/components/PnLChart";
import { DrawdownChart } from "@/components/DrawdownChart";
import { PositionsTable } from "@/components/PositionsTable";
import { StrategyCard } from "@/components/StrategyCard";
import { ExposurePanel } from "@/components/ExposurePanel";
import { HealthBadge } from "@/components/HealthBadge";
import { DriftAlertBanner } from "@/components/DriftAlertBanner";
import { formatPnl, formatPercent, formatNumber } from "@/lib/utils";
import {
  DollarSign, TrendingUp, TrendingDown, Activity, AlertTriangle,
  BarChart3, ShieldCheck, ArrowRight, Play, Cpu, LayoutDashboard,
} from "lucide-react";

export default function DashboardPage() {
  const router = useRouter();
  const { data: snapshot, loading: snapLoading } = usePortfolioSnapshot();
  const { data: history } = usePortfolioHistory();
  const { data: exposure } = useMarketExposure();
  const { data: positions } = usePositions("OPEN");

  const [status, setStatus] = useState<any>(null);
  const [rankings, setRankings] = useState<any[]>([]);
  const [slippage, setSlippage] = useState<any>(null);
  const [systemMode, setSystemMode] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const [strategyNames, setStrategyNames] = useState<string[]>([]);
  const [selectedStrategy, setSelectedStrategy] = useState("");
  const [simResult, setSimResult] = useState<any>(null);
  const [simLoading, setSimLoading] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const [stat, ranks, slip, mode] = await Promise.all([
          api.health.status(),
          api.analytics.strategySummary(7),
          api.analytics.slippageSummary(7),
          api.system.mode().catch(() => null),
        ]);
        setStatus(stat);
        setRankings(ranks.rankings || []);
        setSlippage(slip);
        setSystemMode(mode);
      } catch (e) {
        console.error("Failed to load dashboard data", e);
      } finally {
        setLoading(false);
      }
    }
    load();
    api.strategies.names().then(r => {
      setStrategyNames(r.strategies || []);
      if (r.strategies?.length) setSelectedStrategy(r.strategies[0]);
    }).catch(() => {});
  }, []);

  const killSwitchActive = status?.metrics?.kill_switch_active ?? false;

  async function toggleKillSwitch() {
    try {
      await api.execution.killSwitch();
      setStatus(await api.health.status());
    } catch (e) {
      console.error("Kill switch failed", e);
    }
  }

  async function runSimulation() {
    if (!selectedStrategy) return;
    setSimLoading(true);
    setSimResult(null);
    try {
      const result = await api.backtesting.simulate(selectedStrategy);
      setSimResult(result);
    } catch (e) {
      console.error("Simulation failed", e);
    }
    setSimLoading(false);
  }

  if (snapLoading && !snapshot && loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-black">
        <div className="flex flex-col items-center gap-4">
          <Activity className="h-10 w-10 animate-pulse text-indigo-500" />
          <div className="text-sm font-mono text-gray-500 uppercase tracking-widest">Initializing Operator Workspace...</div>
        </div>
      </div>
    );
  }

  const chartData = (history || []).map((h: any) => ({
    time: new Date(h.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    value: h.portfolio_value || 0,
    pnl: (h.total_realized_pnl || 0) + (h.total_unrealized_pnl || 0),
  }));

  const totalPnl = (snapshot?.unrealized_pnl ?? 0) + (snapshot?.realized_pnl ?? 0);

  return (
    <div className="min-h-screen text-gray-300 font-sans">
      {/* Header */}
      <header className="mb-6 flex flex-col md:flex-row md:items-end justify-between border-b border-[var(--border)] pb-6 gap-4">
        <div>
          <div className="text-[10px] font-semibold text-gray-500 uppercase tracking-widest mb-1">
            Net Liquidation Value
          </div>
          <div className="flex items-baseline gap-3">
            <span className="text-3xl md:text-5xl font-bold text-white tracking-tight">
              ${formatNumber(snapshot?.total_equity ?? 0)}
            </span>
            <span className={`text-lg md:text-xl font-medium ${totalPnl >= 0 ? "text-emerald-500" : "text-rose-500"}`}>
              {totalPnl >= 0 ? "+" : ""}{formatPnl(totalPnl)}
            </span>
          </div>
        </div>
        <div className="flex gap-4 md:gap-6 items-center flex-wrap">
          <div className="text-left md:text-right">
            <div className="text-[10px] font-bold text-gray-600 uppercase tracking-widest mb-1">Drawdown</div>
            <div className="text-lg md:text-xl font-mono text-rose-500 font-bold">
              -{formatPercent(snapshot?.drawdown ?? 0)}
            </div>
          </div>
          <HealthBadge status={status?.status === "healthy" ? "healthy" : "degraded"} />
          {systemMode && (
            <div className="flex items-center gap-1.5 rounded-md border border-yellow-500/30 bg-yellow-500/5 px-2 py-1">
              <span className="h-2 w-2 rounded-full bg-yellow-500" />
              <span className="text-[10px] font-bold uppercase tracking-wider text-yellow-500">{systemMode.mode}</span>
            </div>
          )}
          <div className={`rounded-lg border p-3 flex items-center gap-3 ${killSwitchActive ? "border-rose-900/30" : "border-emerald-900/30"}`}>
            <div>
              <div className="text-[9px] font-bold text-gray-500 uppercase tracking-widest">Kill Switch</div>
              <div className={`text-xs font-bold ${killSwitchActive ? "text-rose-500" : "text-emerald-500"}`}>
                {killSwitchActive ? "HALTED" : "Active"}
              </div>
            </div>
            <button
              onClick={toggleKillSwitch}
              className={`rounded px-3 py-1.5 text-[10px] font-bold text-white transition-colors ${
                killSwitchActive ? "bg-emerald-600 hover:bg-emerald-500" : "bg-rose-600 hover:bg-rose-500"
              }`}
            >
              {killSwitchActive ? "RESUME" : "HALT"}
            </button>
          </div>
        </div>
      </header>

      {/* Summary Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <StatCard
          title="Total Equity"
          value={`$${formatNumber(snapshot?.total_equity ?? 0)}`}
          icon={DollarSign}
          color={totalPnl >= 0 ? "positive" : "negative"}
          loading={snapLoading}
        />
        <StatCard
          title="Unrealized PnL"
          value={formatPnl(snapshot?.unrealized_pnl ?? 0)}
          icon={TrendingUp}
          color={(snapshot?.unrealized_pnl ?? 0) >= 0 ? "positive" : "negative"}
          loading={snapLoading}
        />
        <StatCard
          title="Net Exposure"
          value={`$${formatNumber(snapshot?.net_exposure ?? 0)}`}
          icon={BarChart3}
          loading={snapLoading}
        />
        <StatCard
          title="Open Positions"
          value={`${snapshot?.open_positions_count ?? 0}`}
          icon={Activity}
          subtitle={`Peak: $${formatNumber(snapshot?.peak_value ?? 0)}`}
          loading={snapLoading}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
        {/* Equity Curve */}
        <section className="md:col-span-8 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 md:p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="flex items-center gap-2 text-[10px] font-bold text-gray-400 uppercase tracking-widest">
              <TrendingUp className="h-4 w-4" />
              Portfolio Equity
            </h3>
            <div className="flex gap-2">
              {["1D", "7D", "1M", "ALL"].map((t) => (
                <button
                  key={t}
                  className={`px-2 py-1 text-[10px] font-bold rounded ${
                    t === "7D" ? "bg-gray-800 text-white" : "text-gray-600 hover:text-gray-400"
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
          {history && history.length > 0 ? (
            <PnLChart data={chartData} height={250} color="#6366f1" />
          ) : (
            <div className="flex h-[250px] items-center justify-center text-sm text-gray-600">
              No portfolio history data
            </div>
          )}
        </section>

        {/* Portfolio Stats + Efficiency */}
        <section className="md:col-span-4 space-y-4">
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
            <h3 className="flex items-center gap-2 text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
              <ShieldCheck className="h-4 w-4" />
              Portfolio
            </h3>
            <div className="space-y-3">
              <div className="flex justify-between text-xs">
                <span className="text-gray-500">Gross Exposure</span>
                <span className="text-white font-mono">${formatNumber(snapshot?.net_exposure ?? 0)}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-500">Realized PnL</span>
                <span className={`font-mono ${(snapshot?.realized_pnl ?? 0) >= 0 ? "text-emerald-500" : "text-rose-500"}`}>
                  {formatPnl(snapshot?.realized_pnl ?? 0)}
                </span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-500">Drawdown</span>
                <span className="font-mono text-rose-500">-{formatPercent(snapshot?.drawdown ?? 0)}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-500">Strategies</span>
                <span className="text-white font-mono">{status?.metrics?.active_strategies ?? 0}</span>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
            <h3 className="flex items-center gap-2 text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
              <BarChart3 className="h-4 w-4" />
              Efficiency
            </h3>
            <div className="space-y-3">
              <div className="flex justify-between text-xs border-b border-gray-900 pb-2">
                <span className="text-gray-500">Slippage (7D)</span>
                <span className="font-mono text-white">
                  {slippage ? `${((slippage.avg_slippage || 0) * 100).toFixed(4)}%` : "-"}
                </span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-500">Trades (7D)</span>
                <span className="font-mono text-white">{slippage?.total_trades ?? 0}</span>
              </div>
            </div>
          </div>
        </section>

        {/* Positions Table */}
        <section className="md:col-span-12 rounded-xl border border-[var(--border)] bg-[var(--card)]">
          <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)]">
            <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">
              <Activity className="h-3.5 w-3.5 inline mr-1" />
              Open Positions
            </h3>
            <button
              onClick={() => router.push("/portfolio/positions")}
              className="text-[10px] text-[var(--primary)] hover:underline flex items-center gap-1"
            >
              View All <ArrowRight className="h-3 w-3" />
            </button>
          </div>
          <PositionsTable positions={positions || []} loading={snapLoading} />
        </section>

        {/* Strategy Attribution */}
        <section className="md:col-span-12 grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
            <h3 className="flex items-center gap-2 text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
              <BarChart3 className="h-4 w-4" />
              Strategy Breakdown
            </h3>
            <div className="grid grid-cols-1 gap-2">
              {(snapshot?.strategy_breakdown || []).slice(0, 5).map((s: any) => (
                <div
                  key={s.agent_id}
                  className="flex items-center justify-between py-2 px-2 rounded hover:bg-gray-900/50 cursor-pointer"
                  onClick={() => router.push(`/portfolio/strategies/${s.agent_id}`)}
                >
                  <span className="text-xs text-white">{s.agent_id}</span>
                  <div className="flex items-center gap-4">
                    <span className={`text-xs font-mono font-bold ${s.total_pnl >= 0 ? "text-emerald-500" : "text-rose-500"}`}>
                      {formatPnl(s.total_pnl)}
                    </span>
                    <span className="text-[10px] text-gray-500 w-12 text-right">{s.win_rate.toFixed(0)}%</span>
                    <span className="text-[10px] text-gray-500">{s.trade_count} trades</span>
                  </div>
                </div>
              ))}
              {(!snapshot?.strategy_breakdown || snapshot.strategy_breakdown.length === 0) && (
                <div className="text-sm text-gray-600 text-center py-8">No strategy data</div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
            <h3 className="flex items-center gap-2 text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
              <DollarSign className="h-4 w-4" />
              Top Positions
            </h3>
            <div className="space-y-1">
              {(snapshot?.top_markets || []).slice(0, 6).map((m: any, i: number) => (
                <div key={i} className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-gray-900/50">
                  <span className="text-xs text-white truncate max-w-[180px]">
                    {m.market_slug || m.market_id?.slice(0, 8)}
                  </span>
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-mono text-gray-400">${m.exposure_value.toFixed(2)}</span>
                    <span className={`text-xs font-mono ${m.unrealized_pnl >= 0 ? "text-emerald-500" : "text-rose-500"}`}>
                      {formatPnl(m.unrealized_pnl)}
                    </span>
                  </div>
                </div>
              ))}
              {(!snapshot?.top_markets || snapshot.top_markets.length === 0) && (
                <div className="text-sm text-gray-600 text-center py-8">No positions</div>
              )}
            </div>
          </div>
        </section>

        {/* Exposure Panel */}
        {exposure && (
          <section className="md:col-span-12 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
            <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
              <BarChart3 className="h-3.5 w-3.5 inline mr-1" />
              Market Exposure
            </h3>
            <ExposurePanel
              totalLong={exposure.total_long_exposure}
              totalShort={exposure.total_short_exposure}
              netExposure={exposure.net_exposure}
              concentrationRisk={exposure.concentration_risk_pct}
              largestPositions={exposure.largest_positions || []}
              exposureByMarket={exposure.exposure_by_market || []}
            />
          </section>
        )}

        {/* Strategy cards */}
        <section className="md:col-span-12">
          <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3">
            <Activity className="h-3.5 w-3.5 inline mr-1" />
            Active Strategies
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {(snapshot?.strategy_breakdown || []).slice(0, 6).map((s: any) => (
              <StrategyCard key={s.agent_id} strategy={{
                agent_id: s.agent_id,
                total_trades: s.trade_count,
                wins: Math.round(s.trade_count * s.win_rate / 100),
                losses: Math.round(s.trade_count * (100 - s.win_rate) / 100),
                win_rate: s.win_rate,
                cumulative_pnl: s.total_pnl,
                realized_pnl: s.total_pnl,
                avg_trade_duration_hours: 0,
                max_drawdown: 0,
                total_volume: s.total_volume,
                total_fees: 0,
              }} compact />
            ))}
          </div>
        </section>

        {/* Strategy Simulation Panel */}
        <section className="md:col-span-12 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <h3 className="flex items-center gap-2 text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
            <Cpu className="h-4 w-4" />
            Strategy Simulation
          </h3>
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <label className="block text-[10px] text-gray-600 uppercase tracking-wider mb-1">Strategy</label>
              <select
                value={selectedStrategy}
                onChange={(e) => setSelectedStrategy(e.target.value)}
                className="rounded border border-gray-800 bg-gray-900 px-3 py-2 text-sm text-white focus:outline-none focus:border-gray-600"
              >
                {strategyNames.map((name) => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
            </div>
            <button
              onClick={runSimulation}
              disabled={simLoading || !selectedStrategy}
              className="flex items-center gap-2 rounded bg-indigo-600 px-4 py-2 text-xs font-bold text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors"
            >
              {simLoading ? <Activity className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
              {simLoading ? "Running..." : "Run Simulation"}
            </button>
          </div>

          {simResult && (
            <div className="mt-6 grid grid-cols-2 md:grid-cols-5 gap-4">
              <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-3">
                <div className="text-[10px] text-gray-500 uppercase tracking-wider">Total P&L</div>
                <div className={`text-lg font-bold font-mono mt-1 ${(simResult.metrics?.total_pnl || 0) >= 0 ? "text-emerald-500" : "text-rose-500"}`}>
                  {formatPnl(simResult.metrics?.total_pnl || 0)}
                </div>
              </div>
              <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-3">
                <div className="text-[10px] text-gray-500 uppercase tracking-wider">Win Rate</div>
                <div className="text-lg font-bold font-mono mt-1 text-white">{(simResult.metrics?.win_rate || 0) * 100}%</div>
              </div>
              <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-3">
                <div className="text-[10px] text-gray-500 uppercase tracking-wider">Sharpe</div>
                <div className="text-lg font-bold font-mono mt-1 text-white">{(simResult.metrics?.sharpe_ratio || 0).toFixed(2)}</div>
              </div>
              <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-3">
                <div className="text-[10px] text-gray-500 uppercase tracking-wider">Max Drawdown</div>
                <div className="text-lg font-bold font-mono mt-1 text-rose-500">{(simResult.metrics?.max_drawdown || 0) * 100}%</div>
              </div>
              <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-3">
                <div className="text-[10px] text-gray-500 uppercase tracking-wider">Trades</div>
                <div className="text-lg font-bold font-mono mt-1 text-white">{simResult.metrics?.total_trades || 0}</div>
              </div>
            </div>
          )}
        </section>
      </div>

      {/* Footer status bar */}
      <footer className="mt-8 border-t border-gray-900 pt-3 flex items-center justify-between text-[8px] font-bold text-gray-600 uppercase tracking-[0.2em]">
        <div className="flex items-center gap-4">
          <span>Last Update: {status?.timestamp ? new Date(status.timestamp).toLocaleTimeString() : "---"}</span>
          <span className="hidden md:inline">Env: PROD</span>
        </div>
        <div className="flex items-center gap-4">
          <span className={killSwitchActive ? "text-rose-500/50" : "text-emerald-500/50"}>
            {killSwitchActive ? "HALTED" : "Live"}
          </span>
          <span className="hidden md:inline">Polymarket Intel</span>
        </div>
      </footer>
    </div>
  );
}
