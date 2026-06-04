"use client";

import { useShadowExecutions, useShadowStrategies, useShadowPerformance, useShadowAnalytics, useShadowBenchmarks, useShadowPromotions, useTournamentRankings, useAllAllocations, useSimulator, useAutoPromotions, useResearchRegistry, useResearchChampion, useResearchHealth, usePortfolioReport, useResearchSignals, useResearchConsensus, useResearchAgentHealth, useResearchRegistryStats, useResearchStatus } from "@/lib/hooks";
import { StatCard } from "@/components/StatCard";
import { formatPnl, formatNumber } from "@/lib/utils";
import { Activity, Gauge, TrendingUp, BarChart3, Zap, DollarSign, AlertTriangle, Shield, Target, Award, Trophy, PieChart, TrendingDown, BookOpen, Swords, Heart, FileText, Microscope, GitCompare, Cpu } from "lucide-react";
import { useState, useCallback } from "react";
import { api } from "@/lib/api";

type Tab = "overview" | "executions" | "strategies" | "analytics" | "promotion" | "rankings" | "allocations" | "simulator" | "registry" | "champions" | "health" | "reports" | "signals" | "consensus" | "agents";

export default function ShadowPage() {
  const [tab, setTab] = useState<Tab>("overview");
  const [syncing, setSyncing] = useState(false);
  const { data: executionsData, loading: execLoading, refetch: refetchExecs } = useShadowExecutions();
  const { data: strategiesData, loading: stratLoading, refetch: refetchStrats } = useShadowStrategies();
  const { data: perf, loading: perfLoading, refetch: refetchPerf } = useShadowPerformance();
  const { data: analyticsData, loading: analyticsLoading, refetch: refetchAnalytics } = useShadowAnalytics();
  const { data: benchmarksData, loading: benchmarksLoading } = useShadowBenchmarks();
  const { data: promotionsData, loading: promotionsLoading, refetch: refetchPromotions } = useShadowPromotions();
  const { data: rankingsData, loading: rankingsLoading } = useTournamentRankings();
  const { data: allAllocationsData, loading: allocationsLoading } = useAllAllocations();
  const { data: simData, loading: simLoading } = useSimulator();
  const { data: autoPromoData, loading: autoPromoLoading } = useAutoPromotions();
  const { data: registryData, loading: registryLoading } = useResearchRegistry();
  const { data: championData, loading: championLoading } = useResearchChampion();
  const { data: healthData, loading: healthLoading } = useResearchHealth();
  const { data: portfolioReportData, loading: reportLoading } = usePortfolioReport();
  const { data: researchSignals, loading: signalsLoading, refetch: refetchSignals } = useResearchSignals();
  const { data: researchConsensus, loading: consensusLoading } = useResearchConsensus();
  const { data: agentHealth, loading: agentHealthLoading } = useResearchAgentHealth();
  const { data: registryStats, loading: regStatsLoading } = useResearchRegistryStats();
  const { data: researchStatus, loading: statusLoading, refetch: refetchStatus } = useResearchStatus();

  const executions = executionsData?.executions || [];
  const strategies = strategiesData?.strategies || [];
  const analytics = analyticsData?.analytics || [];
  const benchmarks = benchmarksData?.benchmarks || [];
  const promotions = promotionsData?.promotions || [];
  const totalPnl = perf?.total_pnl ?? 0;
  const winRate = perf?.win_rate ?? 0;
  const totalExecs = perf?.total_executions ?? 0;
  const openExecs = perf?.open_executions ?? 0;
  const closedExecs = perf?.closed_executions ?? 0;
  const totalWins = perf?.win_count ?? 0;
  const totalLosses = perf?.loss_count ?? 0;
  const sharpe = perf?.sharpe ?? 0;

  const handleRunPipeline = async () => {
    try {
      await api.researchAgents.run();
      refetchSignals();
      refetchStatus();
    } catch (e) {
      console.error("Pipeline run failed", e);
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      await api.shadow.sync();
      await api.shadow.refreshPrices();
      refetchExecs();
      refetchStrats();
      refetchPerf();
      refetchAnalytics();
      refetchPromotions();
    } finally {
      setSyncing(false);
    }
  };

  const tabs: { key: Tab; label: string; icon: React.ReactNode }[] = [
    { key: "overview", label: "Overview", icon: <Activity className="h-3 w-3" /> },
    { key: "executions", label: "Executions", icon: <BarChart3 className="h-3 w-3" /> },
    { key: "strategies", label: "Strategies", icon: <Target className="h-3 w-3" /> },
    { key: "analytics", label: "Analytics", icon: <Gauge className="h-3 w-3" /> },
    { key: "promotion", label: "Promotion", icon: <Award className="h-3 w-3" /> },
    { key: "rankings", label: "Rankings", icon: <Trophy className="h-3 w-3" /> },
    { key: "allocations", label: "Allocations", icon: <PieChart className="h-3 w-3" /> },
    { key: "simulator", label: "Simulator", icon: <TrendingDown className="h-3 w-3" /> },
    { key: "registry", label: "Registry", icon: <BookOpen className="h-3 w-3" /> },
    { key: "champions", label: "Champions", icon: <Swords className="h-3 w-3" /> },
    { key: "health", label: "Health", icon: <Heart className="h-3 w-3" /> },
    { key: "reports", label: "Reports", icon: <FileText className="h-3 w-3" /> },
    { key: "signals", label: "Signals", icon: <Microscope className="h-3 w-3" /> },
    { key: "consensus", label: "Consensus", icon: <GitCompare className="h-3 w-3" /> },
    { key: "agents", label: "Agents", icon: <Cpu className="h-3 w-3" /> },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Shadow Trading</h1>
          <p className="text-[10px] text-gray-500 uppercase tracking-wider">
            Hypothetical execution simulation — no live orders
          </p>
        </div>
        <button
          onClick={handleSync}
          disabled={syncing}
          className="text-[10px] px-3 py-1.5 border border-border rounded hover:border-gray-500 transition-colors disabled:opacity-50"
        >
          {syncing ? "Syncing..." : "Sync Signals"}
        </button>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard
          title="Total Shadow PnL"
          value={formatPnl(totalPnl)}
          icon={DollarSign}
          color={totalPnl >= 0 ? "positive" : "negative"}
          loading={perfLoading}
        />
        <StatCard
          title="Win Rate"
          value={`${(winRate * 100).toFixed(1)}%`}
          icon={TrendingUp}
          color={winRate >= 0.5 ? "positive" : "negative"}
          loading={perfLoading}
        />
        <StatCard
          title="Total Executions"
          value={`${totalExecs}`}
          icon={Activity}
          loading={perfLoading}
        />
        <StatCard
          title="Sharpe"
          value={sharpe.toFixed(2)}
          icon={Zap}
          color={sharpe >= 1.0 ? "positive" : sharpe >= 0 ? "default" : "negative"}
          loading={perfLoading}
        />
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[var(--border)] pb-2 overflow-x-auto">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex items-center gap-1.5 text-[10px] uppercase tracking-wider px-3 py-1.5 rounded-t transition-colors whitespace-nowrap ${
              tab === t.key
                ? "text-white border-b-2 border-[var(--primary)]"
                : "text-gray-500 hover:text-gray-300"
            }`}
          >
            {t.icon}
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === "overview" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
            <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
              <Gauge className="h-3.5 w-3.5 inline mr-1" />
              Performance Summary
            </h2>
            <div className="space-y-3">
              {[
                { label: "Total Realized PnL", value: formatPnl(perf?.total_realized_pnl ?? 0), color: (perf?.total_realized_pnl ?? 0) >= 0 ? "text-emerald-500" : "text-red-500" },
                { label: "Total Unrealized PnL", value: formatPnl(perf?.total_unrealized_pnl ?? 0), color: (perf?.total_unrealized_pnl ?? 0) >= 0 ? "text-emerald-500" : "text-red-500" },
                { label: "Avg PnL / Trade", value: formatPnl(perf?.avg_pnl ?? 0), color: (perf?.avg_pnl ?? 0) >= 0 ? "text-emerald-500" : "text-red-500" },
                { label: "Strategies Tracked", value: `${perf?.strategy_count ?? 0}`, color: "text-white" },
              ].map((r) => (
                <div key={r.label} className="flex items-center justify-between py-2 border-b border-gray-900">
                  <span className="text-xs text-gray-400">{r.label}</span>
                  <span className={`text-xs font-bold font-mono ${r.color}`}>{r.value}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
            <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
              <BarChart3 className="h-3.5 w-3.5 inline mr-1" />
              Execution Breakdown
            </h2>
            <div className="space-y-3">
              {[
                { label: "Open Executions", value: `${openExecs}`, color: "text-amber-500" },
                { label: "Closed Executions", value: `${closedExecs}`, color: "text-white" },
                { label: "Win / Loss", value: `${totalWins}W / ${totalLosses}L`, color: totalWins > totalLosses ? "text-emerald-500" : "text-red-500" },
                { label: "Win Rate", value: `${(winRate * 100).toFixed(1)}%`, color: winRate >= 0.5 ? "text-emerald-500" : "text-red-500" },
              ].map((r) => (
                <div key={r.label} className="flex items-center justify-between py-2 border-b border-gray-900">
                  <span className="text-xs text-gray-400">{r.label}</span>
                  <span className={`text-xs font-bold font-mono ${r.color}`}>{r.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {tab === "executions" && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">
              <Activity className="h-3.5 w-3.5 inline mr-1" />
              Shadow Executions
            </h2>
            <span className="text-xs text-muted-foreground">{executions.length} total</span>
          </div>
          {execLoading && <div className="text-center py-8 text-xs text-muted-foreground">Loading...</div>}
          {!execLoading && executions.length === 0 && (
            <div className="text-center py-8 text-xs text-muted-foreground">
              No executions yet. Click "Sync Signals" to process signals.
            </div>
          )}
          {!execLoading && executions.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-gray-800 text-[10px] text-gray-500 uppercase tracking-wider">
                    <th className="text-left py-2 pr-2">Strategy</th>
                    <th className="text-left py-2 pr-2">Direction</th>
                    <th className="text-right py-2 pr-2">Entry</th>
                    <th className="text-right py-2 pr-2">Current</th>
                    <th className="text-right py-2 pr-2">Realized</th>
                    <th className="text-right py-2 pr-2">Unrealized</th>
                    <th className="text-right py-2 pr-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {executions.map((e: any) => (
                    <tr key={e.id} className="border-b border-gray-900 hover:bg-gray-900/30">
                      <td className="py-2 pr-2 text-gray-300">{e.strategy}</td>
                      <td className="py-2 pr-2">
                        <span className={e.direction === "buy" ? "text-emerald-500" : "text-rose-500"}>{e.direction.toUpperCase()}</span>
                      </td>
                      <td className="py-2 pr-2 text-right font-mono text-gray-300">{e.entry_price?.toFixed(4)}</td>
                      <td className="py-2 pr-2 text-right font-mono text-gray-300">{e.current_price?.toFixed(4) ?? "-"}</td>
                      <td className={`py-2 pr-2 text-right font-mono ${(e.realized_pnl ?? 0) >= 0 ? "text-emerald-500" : "text-red-500"}`}>
                        {e.realized_pnl != null ? formatPnl(e.realized_pnl) : "-"}
                      </td>
                      <td className={`py-2 pr-2 text-right font-mono ${(e.unrealized_pnl ?? 0) >= 0 ? "text-emerald-500" : "text-red-500"}`}>
                        {e.unrealized_pnl != null ? formatPnl(e.unrealized_pnl) : "-"}
                      </td>
                      <td className="py-2 text-right">
                        <span className={`text-[10px] px-1.5 py-0.5 rounded ${e.status === "open" ? "bg-amber-500/10 text-amber-400" : "bg-emerald-500/10 text-emerald-400"}`}>
                          {e.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === "strategies" && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
            <Target className="h-3.5 w-3.5 inline mr-1" />
            Strategy Performance (Shadow)
          </h2>
          {stratLoading && <div className="text-center py-8 text-xs text-muted-foreground">Loading...</div>}
          {!stratLoading && strategies.length === 0 && (
            <div className="text-center py-8 text-xs text-muted-foreground">No strategy data yet.</div>
          )}
          {!stratLoading && strategies.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-gray-800 text-[10px] text-gray-500 uppercase tracking-wider">
                    <th className="text-left py-2 pr-2">Strategy</th>
                    <th className="text-right py-2 pr-2">Total</th>
                    <th className="text-right py-2 pr-2">Closed</th>
                    <th className="text-right py-2 pr-2">Open</th>
                    <th className="text-right py-2 pr-2">Realized PnL</th>
                    <th className="text-right py-2 pr-2">Win Rate</th>
                    <th className="text-right py-2 pr-2">Sharpe</th>
                  </tr>
                </thead>
                <tbody>
                  {strategies.map((s: any) => (
                    <tr key={s.strategy} className="border-b border-gray-900 hover:bg-gray-900/30">
                      <td className="py-2 pr-2 text-gray-300 font-medium">{s.strategy}</td>
                      <td className="py-2 pr-2 text-right font-mono text-gray-300">{s.total_executions}</td>
                      <td className="py-2 pr-2 text-right font-mono text-gray-300">{s.closed_executions}</td>
                      <td className="py-2 pr-2 text-right font-mono text-gray-300">{s.open_executions}</td>
                      <td className={`py-2 pr-2 text-right font-mono ${s.total_realized_pnl >= 0 ? "text-emerald-500" : "text-red-500"}`}>
                        {formatPnl(s.total_realized_pnl)}
                      </td>
                      <td className="py-2 pr-2 text-right font-mono text-gray-300">{(s.win_rate * 100).toFixed(1)}%</td>
                      <td className="py-2 pr-2 text-right font-mono text-gray-300">{s.sharpe.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === "analytics" && (
        <div className="space-y-6">
          {analyticsLoading && <div className="text-center py-8 text-xs text-muted-foreground">Loading analytics...</div>}
          {!analyticsLoading && analytics.length === 0 && (
            <div className="text-center py-8 text-xs text-muted-foreground">No analytics data yet.</div>
          )}
          {!analyticsLoading && analytics.length > 0 && (
            <>
              {/* KPI cards */}
              {analytics.map((a: any) => (
                <div key={a.strategy} className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                  <h3 className="text-xs font-bold text-white mb-4">{a.strategy}</h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {[
                      { label: "Sharpe", value: a.sharpe_ratio.toFixed(2), color: a.sharpe_ratio >= 1 ? "text-emerald-500" : a.sharpe_ratio >= 0 ? "text-amber-500" : "text-red-500" },
                      { label: "Sortino", value: a.sortino_ratio.toFixed(2), color: a.sortino_ratio >= 1 ? "text-emerald-500" : "text-amber-500" },
                      { label: "Max Drawdown", value: `${(a.max_drawdown * 100).toFixed(1)}%`, color: a.max_drawdown <= 0.15 ? "text-emerald-500" : "text-red-500" },
                      { label: "Profit Factor", value: a.profit_factor > 0 ? a.profit_factor.toFixed(2) : "-", color: a.profit_factor >= 1.5 ? "text-emerald-500" : a.profit_factor >= 1 ? "text-amber-500" : "text-red-500" },
                    ].map((kpi) => (
                      <div key={kpi.label} className="text-center p-3 rounded-lg border border-gray-800">
                        <div className={`text-lg font-bold font-mono ${kpi.color}`}>{kpi.value}</div>
                        <div className="text-[9px] text-muted-foreground uppercase mt-0.5">{kpi.label}</div>
                      </div>
                    ))}
                    <div className="text-center p-3 rounded-lg border border-gray-800">
                      <div className={`text-lg font-bold font-mono ${a.expectancy >= 0 ? "text-emerald-500" : "text-red-500"}`}>
                        {a.expectancy.toFixed(4)}
                      </div>
                      <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Expectancy</div>
                    </div>
                    <div className="text-center p-3 rounded-lg border border-gray-800">
                      <div className="text-lg font-bold font-mono text-white">{a.win_count}W / {a.loss_count}L</div>
                      <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Win / Loss</div>
                    </div>
                    <div className="text-center p-3 rounded-lg border border-gray-800">
                      <div className="text-lg font-bold font-mono text-white">{a.total_signals}</div>
                      <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Signals</div>
                    </div>
                    <div className="text-center p-3 rounded-lg border border-gray-800">
                      <div className="text-lg font-bold font-mono text-white">{a.average_holding_time_hours.toFixed(1)}h</div>
                      <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Avg Hold</div>
                    </div>
                  </div>

                  {/* Benchmark comparison */}
                  {benchmarks.filter((b: any) => b.strategy === a.strategy).map((b: any) => (
                    <div key={b.strategy} className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4 pt-4 border-t border-gray-800">
                      <div className="text-center p-2 rounded-lg border border-gray-800">
                        <div className={`text-sm font-bold font-mono ${b.alpha >= 0 ? "text-emerald-500" : "text-red-500"}`}>
                          {b.alpha.toFixed(4)}
                        </div>
                        <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Alpha</div>
                      </div>
                      <div className="text-center p-2 rounded-lg border border-gray-800">
                        <div className={`text-sm font-bold font-mono ${b.excess_return >= 0 ? "text-emerald-500" : "text-red-500"}`}>
                          {formatPnl(b.excess_return)}
                        </div>
                        <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Excess Return</div>
                      </div>
                      <div className="text-center p-2 rounded-lg border border-gray-800">
                        <div className={`text-sm font-bold font-mono ${b.information_ratio >= 0 ? "text-emerald-500" : "text-red-500"}`}>
                          {b.information_ratio.toFixed(2)}
                        </div>
                        <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Info Ratio</div>
                      </div>
                      <div className="text-center p-2 rounded-lg border border-gray-800">
                        <div className="text-sm font-bold font-mono text-white">{formatPnl(b.buy_hold_yes_return)}</div>
                        <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Buy-Hold YES</div>
                      </div>
                    </div>
                  ))}
                </div>
              ))}
            </>
          )}
        </div>
      )}

      {tab === "promotion" && (
        <div className="space-y-6">
          {promotionsLoading && <div className="text-center py-8 text-xs text-muted-foreground">Loading promotion data...</div>}
          {!promotionsLoading && promotions.length === 0 && (
            <div className="text-center py-8 text-xs text-muted-foreground">No strategies eligible for promotion evaluation.</div>
          )}
          {!promotionsLoading && promotions.length > 0 && (
            <>
              {/* Strategy ranking */}
              <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
                  <Award className="h-3.5 w-3.5 inline mr-1" />
                  Strategy Promotion Ranking
                </h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-gray-800 text-[10px] text-gray-500 uppercase tracking-wider">
                        <th className="text-left py-2 pr-2">Rank</th>
                        <th className="text-left py-2 pr-2">Strategy</th>
                        <th className="text-center py-2 pr-2">Score</th>
                        <th className="text-center py-2 pr-2">Current</th>
                        <th className="text-center py-2 pr-2">Recommended</th>
                        <th className="text-left py-2 pr-2">Blockers</th>
                      </tr>
                    </thead>
                    <tbody>
                      {promotions
                        .sort((a: any, b: any) => b.confidence_score - a.confidence_score)
                        .map((p: any, i: number) => (
                        <tr key={p.strategy} className="border-b border-gray-900 hover:bg-gray-900/30">
                          <td className="py-2 pr-2 text-muted-foreground font-mono">#{i + 1}</td>
                          <td className="py-2 pr-2 text-gray-300 font-medium">{p.strategy}</td>
                          <td className="py-2 pr-2 text-center">
                            <div className="inline-flex items-center gap-1">
                              <div className="w-16 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                                <div
                                  className={`h-full rounded-full ${p.confidence_score >= 80 ? "bg-emerald-500" : p.confidence_score >= 50 ? "bg-amber-500" : "bg-red-500"}`}
                                  style={{ width: `${p.confidence_score}%` }}
                                />
                              </div>
                              <span className="font-mono text-[10px] text-white">{p.confidence_score.toFixed(0)}</span>
                            </div>
                          </td>
                          <td className="py-2 pr-2 text-center">
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-400">{p.current_tier}</span>
                          </td>
                          <td className="py-2 pr-2 text-center">
                            <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${
                              p.recommended_tier === "LIVE" ? "bg-emerald-500/10 text-emerald-400" :
                              p.recommended_tier === "PAPER" ? "bg-amber-500/10 text-amber-400" :
                              "bg-gray-800 text-gray-400"
                            }`}>
                              {p.recommended_tier}
                            </span>
                          </td>
                          <td className="py-2 text-left">
                            <div className="flex flex-wrap gap-1">
                              {p.blockers.length === 0 && <span className="text-emerald-500 text-[10px]">None</span>}
                              {p.blockers.map((b: string, j: number) => (
                                <span key={j} className="text-[9px] text-red-400 bg-red-500/5 px-1 py-0.5 rounded">{b}</span>
                              ))}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Detail cards */}
              {promotions.sort((a: any, b: any) => b.confidence_score - a.confidence_score).map((p: any) => (
                <div key={p.strategy} className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-xs font-bold text-white">{p.strategy}</h3>
                    <div className="flex items-center gap-3">
                      <div className="text-right">
                        <div className="text-[9px] text-muted-foreground uppercase">Current</div>
                        <div className="text-xs font-mono text-gray-400">{p.current_tier}</div>
                      </div>
                      <Shield className="h-4 w-4 text-gray-600" />
                      <div className="text-right">
                        <div className="text-[9px] text-muted-foreground uppercase">Recommended</div>
                        <div className={`text-xs font-bold font-mono ${
                          p.recommended_tier === "LIVE" ? "text-emerald-400" :
                          p.recommended_tier === "PAPER" ? "text-amber-400" : "text-gray-400"
                        }`}>{p.recommended_tier}</div>
                      </div>
                    </div>
                  </div>

                  {/* Confidence gauge */}
                  <div className="flex items-center gap-4 mb-4">
                    <div className="relative w-16 h-16">
                      <svg className="w-16 h-16 -rotate-90" viewBox="0 0 64 64">
                        <circle cx="32" cy="32" r="28" fill="none" stroke="rgb(31,41,55)" strokeWidth="4" />
                        <circle
                          cx="32" cy="32" r="28" fill="none"
                          stroke={p.confidence_score >= 80 ? "rgb(52,211,153)" : p.confidence_score >= 50 ? "rgb(251,191,36)" : "rgb(239,68,68)"}
                          strokeWidth="4"
                          strokeDasharray={`${(p.confidence_score / 100) * 176} 176`}
                          strokeLinecap="round"
                        />
                      </svg>
                      <div className="absolute inset-0 flex items-center justify-center">
                        <span className="text-xs font-bold font-mono text-white">{p.confidence_score.toFixed(0)}</span>
                      </div>
                    </div>
                    <div>
                      <div className="text-[9px] text-muted-foreground uppercase">Confidence Score</div>
                      <div className={`text-xs font-bold ${p.confidence_score >= 80 ? "text-emerald-400" : p.confidence_score >= 50 ? "text-amber-400" : "text-red-400"}`}>
                        {p.confidence_score >= 80 ? "Strong" : p.confidence_score >= 50 ? "Moderate" : "Weak"}
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <h4 className="text-[9px] text-gray-500 uppercase tracking-wider mb-2">Reasons</h4>
                      {p.reasons.length === 0 && <div className="text-[10px] text-muted-foreground italic">None</div>}
                      {p.reasons.map((r: string, j: number) => (
                        <div key={j} className="flex items-start gap-1.5 py-1">
                          <span className="text-emerald-500 text-[10px] mt-0.5">+</span>
                          <span className="text-[10px] text-gray-300">{r}</span>
                        </div>
                      ))}
                    </div>
                    <div>
                      <h4 className="text-[9px] text-gray-500 uppercase tracking-wider mb-2">Blockers</h4>
                      {p.blockers.length === 0 && <div className="text-[10px] text-emerald-500">None — ready for promotion!</div>}
                      {p.blockers.map((b: string, j: number) => (
                        <div key={j} className="flex items-start gap-1.5 py-1">
                          <span className="text-red-500 text-[10px] mt-0.5">!</span>
                          <span className="text-[10px] text-gray-300">{b}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </>
          )}
        </div>
      )}

      {tab === "rankings" && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
            <Trophy className="h-3.5 w-3.5 inline mr-1" />
            Strategy Tournament Rankings
          </h2>
          {rankingsLoading && <div className="text-center py-8 text-xs text-muted-foreground">Loading rankings...</div>}
          {!rankingsLoading && (!rankingsData?.rankings || rankingsData.rankings.length === 0) && (
            <div className="text-center py-8 text-xs text-muted-foreground">No strategies to rank.</div>
          )}
          {!rankingsLoading && rankingsData?.rankings && rankingsData.rankings.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-gray-800 text-[10px] text-gray-500 uppercase tracking-wider">
                    <th className="text-left py-2 pr-2">Rank</th>
                    <th className="text-left py-2 pr-2">Strategy</th>
                    <th className="text-left py-2 pr-2">Score</th>
                    <th className="text-left py-2 pr-2">Confidence</th>
                    <th className="text-left py-2 pr-2">Tier</th>
                    <th className="text-right py-2 pr-2">Sharpe</th>
                    <th className="text-right py-2 pr-2">Sortino</th>
                    <th className="text-right py-2 pr-2">Win Rate</th>
                    <th className="text-right py-2 pr-2">Drawdown</th>
                    <th className="text-right py-2 pr-2">Alpha</th>
                    <th className="text-right py-2 pr-2">Trades</th>
                  </tr>
                </thead>
                <tbody>
                  {rankingsData.rankings.map((r: any) => (
                    <tr key={r.strategy} className="border-b border-gray-900 hover:bg-gray-900/30">
                      <td className="py-2 pr-2">
                        <span className={`font-mono font-bold ${r.rank <= 3 ? "text-amber-500" : "text-muted-foreground"}`}>
                          #{r.rank}
                        </span>
                      </td>
                      <td className="py-2 pr-2 text-gray-300 font-medium">{r.strategy}</td>
                      <td className="py-2 pr-2">
                        <div className="flex items-center gap-1.5">
                          <div className="w-16 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                            <div className={`h-full rounded-full ${r.score >= 70 ? "bg-emerald-500" : r.score >= 40 ? "bg-amber-500" : "bg-red-500"}`}
                              style={{ width: `${Math.min(r.score, 100)}%` }}
                            />
                          </div>
                          <span className="font-mono text-[10px] text-white">{r.score.toFixed(1)}</span>
                        </div>
                      </td>
                      <td className="py-2 pr-2">
                        <span className={`font-mono text-[10px] ${r.confidence >= 80 ? "text-emerald-400" : r.confidence >= 50 ? "text-amber-400" : "text-red-400"}`}>
                          {r.confidence.toFixed(0)}
                        </span>
                      </td>
                      <td className="py-2 pr-2">
                        <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                          r.tier === "LIVE" ? "bg-emerald-500/10 text-emerald-400" :
                          r.tier === "PAPER" ? "bg-amber-500/10 text-amber-400" :
                          "bg-gray-800 text-gray-400"
                        }`}>{r.tier}</span>
                      </td>
                      <td className="py-2 pr-2 text-right font-mono text-gray-300">{r.sharpe.toFixed(2)}</td>
                      <td className="py-2 pr-2 text-right font-mono text-gray-300">{r.sortino.toFixed(2)}</td>
                      <td className="py-2 pr-2 text-right font-mono text-gray-300">{(r.win_rate * 100).toFixed(1)}%</td>
                      <td className="py-2 pr-2 text-right font-mono text-gray-300">{(r.max_drawdown * 100).toFixed(1)}%</td>
                      <td className={`py-2 pr-2 text-right font-mono ${r.alpha >= 0 ? "text-emerald-500" : "text-red-500"}`}>
                        {r.alpha.toFixed(4)}
                      </td>
                      <td className="py-2 pr-2 text-right font-mono text-gray-300">{r.total_trades}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === "allocations" && (
        <div className="space-y-6">
          {allocationsLoading && <div className="text-center py-8 text-xs text-muted-foreground">Loading allocations...</div>}
          {!allocationsLoading && allAllocationsData?.modes && allAllocationsData.modes.map((modeResult: any) => (
            <div key={modeResult.mode} className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
              <h3 className="text-xs font-bold text-white mb-1 capitalize">{modeResult.mode} Allocation</h3>
              <p className="text-[10px] text-muted-foreground mb-4">{modeResult.description}</p>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-gray-800 text-[10px] text-gray-500 uppercase tracking-wider">
                      <th className="text-left py-2 pr-2">Strategy</th>
                      <th className="text-right py-2 pr-2">Allocation %</th>
                      <th className="text-right py-2 pr-2">Capital</th>
                      <th className="text-right py-2 pr-2">Risk Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {modeResult.allocations.map((a: any) => (
                      <tr key={a.strategy} className="border-b border-gray-900 hover:bg-gray-900/30">
                        <td className="py-2 pr-2 text-gray-300">{a.strategy}</td>
                        <td className="py-2 pr-2 text-right font-mono text-white">{a.allocation_pct.toFixed(1)}%</td>
                        <td className="py-2 pr-2 text-right font-mono text-gray-300">${a.capital_assigned.toLocaleString()}</td>
                        <td className="py-2 pr-2 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <div className="w-12 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                              <div className={`h-full rounded-full ${a.risk_score <= 0.3 ? "bg-emerald-500" : a.risk_score <= 0.6 ? "bg-amber-500" : "bg-red-500"}`}
                                style={{ width: `${a.risk_score * 100}%` }}
                              />
                            </div>
                            <span className="font-mono text-[10px] text-gray-400">{a.risk_score.toFixed(2)}</span>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === "simulator" && (
        <div className="space-y-6">
          {simLoading && <div className="text-center py-8 text-xs text-muted-foreground">Running simulation...</div>}
          {!simLoading && simData && (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <StatCard title="Starting Capital" value={`$${formatNumber(simData.starting_capital)}`} icon={DollarSign} />
                <StatCard title="Final Equity" value={`$${formatNumber(simData.final_equity)}`} icon={DollarSign}
                  color={simData.total_return >= 0 ? "positive" : "negative"} />
                <StatCard title="Total Return" value={`${(simData.total_return_pct * 100).toFixed(2)}%`} icon={TrendingUp}
                  color={simData.total_return >= 0 ? "positive" : "negative"} />
                <StatCard title="CAGR" value={`${(simData.cagr * 100).toFixed(2)}%`} icon={Gauge}
                  color={simData.cagr >= 0 ? "positive" : "negative"} />
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <StatCard title="Volatility" value={simData.volatility.toFixed(4)} icon={Activity} />
                <StatCard title="Sharpe" value={simData.sharpe.toFixed(2)} icon={Zap}
                  color={simData.sharpe >= 1 ? "positive" : simData.sharpe >= 0 ? "default" : "negative"} />
                <StatCard title="Calmar Ratio" value={simData.calmar_ratio.toFixed(2)} icon={BarChart3}
                  color={simData.calmar_ratio >= 1 ? "positive" : "default"} />
                <StatCard title="Max Drawdown" value={`${(simData.max_drawdown_pct).toFixed(1)}%`} icon={AlertTriangle}
                  color={simData.max_drawdown_pct <= 15 ? "positive" : "negative"} />
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <StatCard title="Profit Factor" value={simData.profit_factor > 100 ? "∞" : simData.profit_factor.toFixed(2)} icon={TrendingUp}
                  color={simData.profit_factor >= 1.5 ? "positive" : "default"} />
                <StatCard title="Recovery Factor" value={simData.recovery_factor.toFixed(2)} icon={Shield}
                  color={simData.recovery_factor >= 1 ? "positive" : "default"} />
                <StatCard title="Total Return $" value={`$${formatNumber(simData.total_return)}`} icon={DollarSign}
                  color={simData.total_return >= 0 ? "positive" : "negative"} />
                <StatCard title="Data Points" value={`${simData.equity_curve?.length || 0}`} icon={BarChart3} />
              </div>
              {autoPromoData?.recommendations && autoPromoData.recommendations.length > 0 && (
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                  <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
                    <Award className="h-3.5 w-3.5 inline mr-1" />
                    Promotion Recommendations
                  </h2>
                  <div className="space-y-2">
                    {autoPromoData.recommendations.map((rec: any) => (
                      <div key={rec.strategy} className="flex items-center justify-between py-2 border-b border-gray-900 text-xs">
                        <div className="flex items-center gap-2">
                          <span className="text-gray-300 font-medium">{rec.strategy}</span>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                            rec.action === "promote" ? "bg-emerald-500/10 text-emerald-400" : "bg-amber-500/10 text-amber-400"
                          }`}>{rec.action}</span>
                          <span className="text-[10px] text-muted-foreground">{rec.from_tier} → {rec.to_tier}</span>
                        </div>
                        <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
                          <span>7d: {rec.score_7d.toFixed(2)}</span>
                          <span>30d: {rec.score_30d.toFixed(2)}</span>
                          <span>window: {rec.window}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ── Registry Tab ──────────────────────── */}
      {tab === "registry" && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
            <BookOpen className="h-3.5 w-3.5 inline mr-1" />
            Strategy Registry
          </h2>
          {registryLoading && <div className="text-center py-8 text-xs text-muted-foreground">Loading...</div>}
          {!registryLoading && (!registryData?.strategies || registryData.strategies.length === 0) && (
            <div className="text-center py-8 text-xs text-muted-foreground">No registered strategies.</div>
          )}
          {!registryLoading && registryData?.strategies && registryData.strategies.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-gray-800 text-[10px] text-gray-500 uppercase tracking-wider">
                    <th className="text-left py-2 pr-2">Name</th>
                    <th className="text-left py-2 pr-2">ID</th>
                    <th className="text-center py-2 pr-2">Status</th>
                    <th className="text-center py-2 pr-2">Version</th>
                    <th className="text-left py-2 pr-2">Owner</th>
                    <th className="text-right py-2">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {registryData.strategies.map((s: any) => (
                    <tr key={s.strategy_id} className="border-b border-gray-900 hover:bg-gray-900/30">
                      <td className="py-2 pr-2 text-gray-300 font-medium">{s.name}</td>
                      <td className="py-2 pr-2 text-gray-400 font-mono text-[10px]">{s.strategy_id}</td>
                      <td className="py-2 pr-2 text-center">
                        <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                          s.status === "live" ? "bg-emerald-500/10 text-emerald-400" :
                          s.status === "paper" ? "bg-blue-500/10 text-blue-400" :
                          s.status === "shadow" ? "bg-amber-500/10 text-amber-400" :
                          s.status === "retired" ? "bg-gray-500/10 text-gray-400" :
                          "bg-purple-500/10 text-purple-400"
                        }`}>{s.status.toUpperCase()}</span>
                      </td>
                      <td className="py-2 pr-2 text-center font-mono text-gray-400">{s.version}</td>
                      <td className="py-2 pr-2 text-gray-400">{s.owner}</td>
                      <td className="py-2 text-right text-gray-500 text-[10px]">{s.created_at ? new Date(s.created_at).toLocaleDateString() : "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── Champions Tab ─────────────────────── */}
      {tab === "champions" && (
        <div className="space-y-6">
          {championLoading && <div className="text-center py-8 text-xs text-muted-foreground">Evaluating...</div>}
          {!championLoading && championData && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                  <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
                    <Trophy className="h-3.5 w-3.5 inline mr-1" />
                    Current Champion
                  </h2>
                  {championData.champion ? (
                    <div>
                      <p className="text-lg font-bold text-white font-mono">{championData.champion}</p>
                      <p className="text-xs text-gray-400 mt-1">Score: {championData.champion_score.toFixed(4)}</p>
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground">No champion identified</p>
                  )}
                </div>
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                  <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
                    <Zap className="h-3.5 w-3.5 inline mr-1" />
                    Recommendation
                  </h2>
                  <span className={`text-lg font-bold ${
                    championData.recommendation === "REPLACE" ? "text-red-400" :
                    championData.recommendation === "WATCH" ? "text-amber-400" : "text-emerald-400"
                  }`}>{championData.recommendation}</span>
                  <p className="text-xs text-gray-400 mt-1">Replacement score: {championData.replacement_score.toFixed(4)}</p>
                </div>
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                  <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
                    <Swords className="h-3.5 w-3.5 inline mr-1" />
                    Top Challengers
                  </h2>
                  <p className="text-2xl font-bold text-white">{championData.challengers?.length || 0}</p>
                  <p className="text-xs text-gray-400 mt-1">Contenders ranked</p>
                </div>
              </div>

              {championData.challengers && championData.challengers.length > 0 && (
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                  <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">Challenger Rankings</h2>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-gray-800 text-[10px] text-gray-500 uppercase tracking-wider">
                          <th className="text-left py-2 pr-2">Rank</th>
                          <th className="text-left py-2 pr-2">Strategy</th>
                          <th className="text-right py-2 pr-2">Score</th>
                          <th className="text-right py-2 pr-2">Sharpe</th>
                          <th className="text-right py-2 pr-2">Win Rate</th>
                          <th className="text-right py-2 pr-2">Drawdown</th>
                          <th className="text-right py-2 pr-2">Tier</th>
                        </tr>
                      </thead>
                      <tbody>
                        {championData.challengers.map((c: any, i: number) => (
                          <tr key={c.strategy || i} className="border-b border-gray-900 hover:bg-gray-900/30">
                            <td className="py-2 pr-2 text-gray-500 font-mono">#{i + 1}</td>
                            <td className="py-2 pr-2 text-gray-300">{c.strategy}</td>
                            <td className="py-2 pr-2 text-right font-mono text-white">{c.score?.toFixed(4)}</td>
                            <td className="py-2 pr-2 text-right font-mono text-gray-300">{c.sharpe_ratio?.toFixed(2)}</td>
                            <td className="py-2 pr-2 text-right font-mono text-gray-300">{c.win_rate != null ? `${(c.win_rate * 100).toFixed(1)}%` : "-"}</td>
                            <td className="py-2 pr-2 text-right font-mono text-gray-300">{c.max_drawdown != null ? `${(c.max_drawdown * 100).toFixed(1)}%` : "-"}</td>
                            <td className="py-2 pr-2 text-right">
                              <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                                c.tier === "LIVE" ? "bg-emerald-500/10 text-emerald-400" :
                                c.tier === "PAPER" ? "bg-blue-500/10 text-blue-400" : "bg-amber-500/10 text-amber-400"
                              }`}>{c.tier}</span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ── Health Tab ─────────────────────────── */}
      {tab === "health" && (
        <div className="space-y-4">
          {healthLoading && <div className="text-center py-8 text-xs text-muted-foreground">Computing health...</div>}
          {!healthLoading && (!healthData?.health || healthData.health.length === 0) && (
            <div className="text-center py-8 text-xs text-muted-foreground">No health data available.</div>
          )}
          {!healthLoading && healthData?.health && healthData.health.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {healthData.health.map((h: any) => (
                <div key={h.strategy} className={`rounded-xl border p-4 ${
                  h.level === "CRITICAL" ? "border-red-500/30 bg-red-950/20" :
                  h.level === "WARNING" ? "border-amber-500/30 bg-amber-950/20" :
                  "border-emerald-500/20 bg-[var(--card)]"
                }`}>
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-xs font-bold text-white">{h.strategy}</h3>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                      h.level === "CRITICAL" ? "bg-red-500/10 text-red-400" :
                      h.level === "WARNING" ? "bg-amber-500/10 text-amber-400" :
                      "bg-emerald-500/10 text-emerald-400"
                    }`}>{h.level}</span>
                  </div>
                  <div className="flex items-center gap-3 mb-3">
                    <div className="relative w-12 h-12">
                      <svg className="w-12 h-12 -rotate-90" viewBox="0 0 36 36">
                        <circle cx="18" cy="18" r="15.5" fill="none" stroke="#1f2937" strokeWidth="3" />
                        <circle cx="18" cy="18" r="15.5" fill="none" stroke={
                          h.score >= 75 ? "#10b981" : h.score >= 50 ? "#f59e0b" : "#ef4444"
                        } strokeWidth="3" strokeDasharray={`${(h.score / 100) * 97.4} 97.4`} />
                      </svg>
                      <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-white">{h.score.toFixed(0)}</span>
                    </div>
                    <div className="text-[10px] text-gray-400 space-y-0.5">
                      <div>PnL trend: <span className={h.pnl_trend >= 0 ? "text-emerald-400" : "text-red-400"}>{h.pnl_trend >= 0 ? "+" : ""}{h.pnl_trend.toFixed(4)}</span></div>
                      <div>Win rate trend: <span className={h.win_rate_trend >= 0 ? "text-emerald-400" : "text-red-400"}>{h.win_rate_trend >= 0 ? "+" : ""}{h.win_rate_trend.toFixed(4)}</span></div>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-[10px]">
                    <div className="text-gray-500">Drift events: <span className="text-gray-300">{h.drift_events}</span></div>
                    <div className="text-gray-500">Breaker events: <span className="text-gray-300">{h.breaker_events}</span></div>
                    <div className="text-gray-500">Latency incidents: <span className="text-gray-300">{h.latency_incidents}</span></div>
                    <div className="text-gray-500">Exec failures: <span className="text-gray-300">{h.execution_failures}</span></div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Reports Tab ────────────────────────── */}
      {tab === "reports" && (
        <div className="space-y-6">
          {reportLoading && <div className="text-center py-8 text-xs text-muted-foreground">Generating report...</div>}
          {!reportLoading && portfolioReportData && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                <StatCard title="Total Strategies" value={`${portfolioReportData.total_strategies}`} icon={BookOpen} />
                <StatCard title="Top Performers" value={`${portfolioReportData.top_performers?.length || 0}`} icon={Trophy} color="positive" />
                <StatCard title="Concentration Risks" value={`${portfolioReportData.concentration_risks?.length || 0}`} icon={AlertTriangle}
                  color={(portfolioReportData.concentration_risks?.length || 0) > 0 ? "negative" : "default"} />
                <StatCard title="Retirement Candidates" value={`${portfolioReportData.retirement_candidates?.length || 0}`} icon={Shield}
                  color={(portfolioReportData.retirement_candidates?.length || 0) > 0 ? "negative" : "default"} />
              </div>

              {portfolioReportData.top_performers && portfolioReportData.top_performers.length > 0 && (
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                  <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
                    <Trophy className="h-3.5 w-3.5 inline mr-1" />
                    Top Performers
                  </h2>
                  <div className="space-y-2">
                    {portfolioReportData.top_performers.map((p: any) => (
                      <div key={p.strategy} className="flex items-center justify-between py-2 border-b border-gray-900 text-xs">
                        <span className="text-gray-300 font-medium">{p.strategy}</span>
                        <div className="flex items-center gap-4">
                          <span className="font-mono text-gray-300">{formatPnl(p.total_pnl)}</span>
                          <span className="font-mono text-gray-500">Sharpe: {p.sharpe?.toFixed(2)}</span>
                          <span className="text-gray-500">WR: {p.win_rate != null ? `${(p.win_rate * 100).toFixed(1)}%` : "-"}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {portfolioReportData.promotion_opportunities && portfolioReportData.promotion_opportunities.length > 0 && (
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                  <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
                    <Award className="h-3.5 w-3.5 inline mr-1" />
                    Promotion Opportunities
                  </h2>
                  <div className="space-y-2">
                    {portfolioReportData.promotion_opportunities.map((p: any) => (
                      <div key={p.strategy} className="flex items-center justify-between py-2 border-b border-gray-900 text-xs">
                        <span className="text-gray-300 font-medium">{p.strategy}</span>
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400">{p.recommended_tier}</span>
                          <span className="font-mono text-gray-400">Confidence: {p.confidence?.toFixed(0)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {portfolioReportData.concentration_risks && portfolioReportData.concentration_risks.length > 0 && (
                <div className="rounded-xl border border-red-500/20 bg-red-950/10 p-4">
                  <h2 className="text-[10px] font-bold text-red-400 uppercase tracking-widest mb-4">
                    <AlertTriangle className="h-3.5 w-3.5 inline mr-1" />
                    Concentration Risks
                  </h2>
                  <div className="space-y-2">
                    {portfolioReportData.concentration_risks.map((c: any) => (
                      <div key={c.strategy} className="flex items-center justify-between py-2 border-b border-red-900/30 text-xs">
                        <span className="text-gray-300 font-medium">{c.strategy}</span>
                        <div className="flex items-center gap-4">
                          <span className="text-red-400 font-mono">{c.exposure_pct}% exposure</span>
                          <span className="font-mono text-gray-400">{formatPnl(c.total_pnl)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {portfolioReportData.retirement_candidates && portfolioReportData.retirement_candidates.length > 0 && (
                <div className="rounded-xl border border-amber-500/20 bg-amber-950/10 p-4">
                  <h2 className="text-[10px] font-bold text-amber-400 uppercase tracking-widest mb-4">
                    <Shield className="h-3.5 w-3.5 inline mr-1" />
                    Retirement Candidates
                  </h2>
                  <div className="space-y-2">
                    {portfolioReportData.retirement_candidates.map((r: any) => (
                      <div key={r.strategy} className="flex items-center justify-between py-2 border-b border-amber-900/30 text-xs">
                        <span className="text-gray-300 font-medium">{r.strategy}</span>
                        <div className="flex items-center gap-2 text-gray-400">
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400">{r.health}</span>
                          <span>Reasons: {r.reasons?.join(", ")}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
          {!reportLoading && !portfolioReportData && (
            <div className="text-center py-8 text-xs text-muted-foreground">No report data available.</div>
          )}
        </div>
      )}

      {/* ── Signals Tab ─────────────────────────── */}
      {tab === "signals" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">
              <Microscope className="h-3.5 w-3.5 inline mr-1" />
              Research Agent Signals
            </h2>
            <button
              onClick={handleRunPipeline}
              className="text-[10px] px-3 py-1.5 border border-border rounded hover:border-gray-500 transition-colors"
            >
              Run Pipeline
            </button>
          </div>

          {signalsLoading && <div className="text-center py-8 text-xs text-muted-foreground">Loading signals...</div>}
          {!signalsLoading && (!researchSignals?.signals || researchSignals.signals.length === 0) && (
            <div className="text-center py-8 text-xs text-muted-foreground">No signals generated yet.</div>
          )}
          {!signalsLoading && researchSignals?.signals && researchSignals.signals.length > 0 && (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <StatCard title="Total Signals" value={`${researchSignals.signals.length}`} icon={Microscope} />
                <StatCard title="Avg Confidence" value={`${(researchSignals.signals.reduce((s: number, sig: any) => s + (sig.confidence || 0), 0) / researchSignals.signals.length * 100).toFixed(1)}%`} icon={Gauge} color="default" />
                <StatCard title="Composition Score" value={`${(researchSignals.signals.reduce((s: number, sig: any) => s + (sig.quality_score || 0), 0) / researchSignals.signals.length * 100).toFixed(1)}%`} icon={Target} color="default" />
                <StatCard title="Lifecycle Stages" value={`${new Set(researchSignals.signals.map((sig: any) => sig.lifecycle || "unknown")).size}`} icon={Activity} />
              </div>
              <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-gray-800 text-[10px] text-gray-500 uppercase tracking-wider">
                        <th className="text-left py-2 pr-2">Signal ID</th>
                        <th className="text-left py-2 pr-2">Agent</th>
                        <th className="text-left py-2 pr-2">Direction</th>
                        <th className="text-left py-2 pr-2">Outcome</th>
                        <th className="text-right py-2 pr-2">Confidence</th>
                        <th className="text-right py-2 pr-2">Quality Score</th>
                        <th className="text-left py-2 pr-2">Lifecycle</th>
                        <th className="text-right py-2">Created</th>
                      </tr>
                    </thead>
                    <tbody>
                      {researchSignals.signals.map((sig: any) => (
                        <tr key={sig.id} className="border-b border-gray-900 hover:bg-gray-900/30">
                          <td className="py-2 pr-2 text-gray-400 font-mono text-[10px]">{sig.id?.substring(0, 8)}</td>
                          <td className="py-2 pr-2 text-gray-300">{sig.agent || sig.source_agent}</td>
                          <td className="py-2 pr-2">
                            <span className={sig.direction === "buy" ? "text-emerald-500" : sig.direction === "sell" ? "text-rose-500" : "text-amber-500"}>
                              {(sig.direction || "unknown").toUpperCase()}
                            </span>
                          </td>
                          <td className="py-2 pr-2 text-gray-300">{sig.outcome || "-"}</td>
                          <td className="py-2 pr-2 text-right">
                            <div className="flex items-center justify-end gap-1.5">
                              <div className="w-16 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                                <div className={`h-full rounded-full ${(sig.confidence || 0) >= 0.7 ? "bg-emerald-500" : (sig.confidence || 0) >= 0.4 ? "bg-amber-500" : "bg-red-500"}`}
                                  style={{ width: `${(sig.confidence || 0) * 100}%` }}
                                />
                              </div>
                              <span className="font-mono text-[10px] text-white">{(sig.confidence * 100).toFixed(0)}%</span>
                            </div>
                          </td>
                          <td className="py-2 pr-2 text-right font-mono">
                            <span className={`text-[10px] ${(sig.quality_score || 0) >= 0.7 ? "text-emerald-400" : (sig.quality_score || 0) >= 0.4 ? "text-amber-400" : "text-red-400"}`}>
                              {(sig.quality_score || 0).toFixed(2)}
                            </span>
                          </td>
                          <td className="py-2 pr-2">
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-400">{sig.lifecycle || "new"}</span>
                          </td>
                          <td className="py-2 text-right text-gray-500 text-[10px]">{sig.generated_at ? new Date(sig.generated_at).toLocaleString() : "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* ── Consensus Tab ───────────────────────── */}
      {tab === "consensus" && (
        <div className="space-y-4">
          <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">
            <GitCompare className="h-3.5 w-3.5 inline mr-1" />
            Agent Consensus
          </h2>

          {consensusLoading && <div className="text-center py-8 text-xs text-muted-foreground">Loading consensus...</div>}
          {!consensusLoading && researchConsensus && (
            <>
              <div className="grid grid-cols-3 gap-3">
                <StatCard title="Approved" value={`${researchConsensus.approved_count ?? 0}`} icon={Award} color="positive" />
                <StatCard title="Rejected" value={`${researchConsensus.rejected_count ?? 0}`} icon={AlertTriangle} color="negative" />
                <StatCard title="Pending" value={`${researchConsensus.pending_count ?? 0}`} icon={Activity} color="default" />
              </div>

              {researchConsensus.approved && researchConsensus.approved.length > 0 && (
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                  <h3 className="text-[10px] font-bold text-emerald-400 uppercase tracking-widest mb-4">Approved Signals</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-gray-800 text-[10px] text-gray-500 uppercase tracking-wider">
                          <th className="text-left py-2 pr-2">Signal ID</th>
                          <th className="text-left py-2 pr-2">Agent</th>
                          <th className="text-left py-2 pr-2">Direction</th>
                          <th className="text-left py-2 pr-2">Outcome</th>
                          <th className="text-right py-2 pr-2">Score</th>
                          <th className="text-left py-2">Type</th>
                        </tr>
                      </thead>
                      <tbody>
                        {researchConsensus.approved.map((sig: any) => (
                          <tr key={sig.id} className="border-b border-gray-900 hover:bg-gray-900/30">
                            <td className="py-2 pr-2 text-gray-400 font-mono text-[10px]">{sig.id?.substring(0, 8)}</td>
                            <td className="py-2 pr-2 text-gray-300">{sig.agent || sig.source_agent}</td>
                            <td className="py-2 pr-2">
                              <span className={sig.direction === "buy" ? "text-emerald-500" : sig.direction === "sell" ? "text-rose-500" : "text-amber-500"}>
                                {(sig.direction || "unknown").toUpperCase()}
                              </span>
                            </td>
                            <td className="py-2 pr-2 text-gray-300">{sig.outcome || "-"}</td>
                            <td className="py-2 pr-2 text-right font-mono text-emerald-400">{(sig.confidence || sig.score || 0).toFixed(2)}</td>
                            <td className="py-2">
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400">{sig.signal_type || "standard"}</span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {researchConsensus.pending && researchConsensus.pending.length > 0 && (
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                  <h3 className="text-[10px] font-bold text-amber-400 uppercase tracking-widest mb-4">Pending Signals</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-gray-800 text-[10px] text-gray-500 uppercase tracking-wider">
                          <th className="text-left py-2 pr-2">Signal ID</th>
                          <th className="text-left py-2 pr-2">Agent</th>
                          <th className="text-left py-2 pr-2">Direction</th>
                          <th className="text-left py-2 pr-2">Outcome</th>
                          <th className="text-right py-2 pr-2">Score</th>
                          <th className="text-left py-2">Type</th>
                        </tr>
                      </thead>
                      <tbody>
                        {researchConsensus.pending.map((sig: any) => (
                          <tr key={sig.id} className="border-b border-gray-900 hover:bg-gray-900/30">
                            <td className="py-2 pr-2 text-gray-400 font-mono text-[10px]">{sig.id?.substring(0, 8)}</td>
                            <td className="py-2 pr-2 text-gray-300">{sig.agent || sig.source_agent}</td>
                            <td className="py-2 pr-2">
                              <span className={sig.direction === "buy" ? "text-emerald-500" : sig.direction === "sell" ? "text-rose-500" : "text-amber-500"}>
                                {(sig.direction || "unknown").toUpperCase()}
                              </span>
                            </td>
                            <td className="py-2 pr-2 text-gray-300">{sig.outcome || "-"}</td>
                            <td className="py-2 pr-2 text-right font-mono text-amber-400">{(sig.confidence || sig.score || 0).toFixed(2)}</td>
                            <td className="py-2">
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400">{sig.signal_type || "standard"}</span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {(!researchConsensus.approved || researchConsensus.approved.length === 0) && (!researchConsensus.pending || researchConsensus.pending.length === 0) && (
                <div className="text-center py-8 text-xs text-muted-foreground">No consensus data available.</div>
              )}
            </>
          )}
        </div>
      )}

      {/* ── Agents Tab ──────────────────────────── */}
      {tab === "agents" && (
        <div className="space-y-4">
          <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">
            <Cpu className="h-3.5 w-3.5 inline mr-1" />
            Research Agents
          </h2>

          {statusLoading && <div className="text-center py-8 text-xs text-muted-foreground">Loading agent status...</div>}
          {!statusLoading && researchStatus && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <StatCard title="Total Signals Generated" value={`${researchStatus.total_signals_generated ?? researchSignals?.signals?.length ?? 0}`} icon={Microscope} />
              <StatCard title="Avg Confidence" value={`${researchStatus.avg_confidence ? (researchStatus.avg_confidence * 100).toFixed(1) + "%" : "-"}`} icon={Gauge} color="default" />
              <StatCard title="Active Agents" value={`${researchStatus.active_agents ?? agentHealth?.agents?.length ?? 0}`} icon={Cpu} color="positive" />
              <StatCard title="Pipeline Status" value={researchStatus.pipeline_status || researchStatus.status || "idle"} icon={Activity}
                color={researchStatus.pipeline_status === "running" ? "default" : "positive"} />
            </div>
          )}

          {/* Agent health cards */}
          {agentHealthLoading && <div className="text-center py-4 text-xs text-muted-foreground">Loading agent health...</div>}
          {!agentHealthLoading && agentHealth?.agents && agentHealth.agents.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {agentHealth.agents.map((agent: any) => (
                <div key={agent.name || agent.id} className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-xs font-bold text-white">{agent.name || agent.id}</h3>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                      agent.status === "healthy" || agent.status === "active" ? "bg-emerald-500/10 text-emerald-400" :
                      agent.status === "degraded" || agent.status === "warning" ? "bg-amber-500/10 text-amber-400" :
                      "bg-red-500/10 text-red-400"
                    }`}>
                      {(agent.status || agent.health_status || "unknown").toUpperCase()}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-[10px]">
                    <div className="text-gray-500">Signals: <span className="text-gray-300">{agent.signals_generated ?? agent.total_signals ?? 0}</span></div>
                    <div className="text-gray-500">Last Run: <span className="text-gray-300">{agent.last_run ? new Date(agent.last_run).toLocaleString() : "-"}</span></div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Agent counts table */}
          {regStatsLoading && <div className="text-center py-4 text-xs text-muted-foreground">Loading registry stats...</div>}
          {!regStatsLoading && registryStats?.agent_counts && registryStats.agent_counts.length > 0 && (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
              <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">Agent Signal Counts</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-gray-800 text-[10px] text-gray-500 uppercase tracking-wider">
                      <th className="text-left py-2 pr-2">Agent Name</th>
                      <th className="text-right py-2 pr-2">Total</th>
                      <th className="text-right py-2 pr-2">Approved</th>
                      <th className="text-right py-2">Rejected</th>
                    </tr>
                  </thead>
                  <tbody>
                    {registryStats.agent_counts.map((ac: any, i: number) => (
                      <tr key={ac.agent_name || ac.agent || i} className="border-b border-gray-900 hover:bg-gray-900/30">
                        <td className="py-2 pr-2 text-gray-300 font-medium">{ac.agent_name || ac.agent}</td>
                        <td className="py-2 pr-2 text-right font-mono text-gray-300">{ac.total ?? ac.count ?? 0}</td>
                        <td className="py-2 pr-2 text-right font-mono text-emerald-400">{ac.approved ?? 0}</td>
                        <td className="py-2 text-right font-mono text-red-400">{ac.rejected ?? 0}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {!agentHealthLoading && (!agentHealth?.agents || agentHealth.agents.length === 0) && !regStatsLoading && (!registryStats?.agent_counts || registryStats.agent_counts.length === 0) && (
            <div className="text-center py-8 text-xs text-muted-foreground">No agent data available.</div>
          )}
        </div>
      )}
    </div>
  );
}
