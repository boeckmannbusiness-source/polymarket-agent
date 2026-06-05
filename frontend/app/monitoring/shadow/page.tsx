"use client";

import { useShadowExecutions, useShadowStrategies, useShadowPerformance, useShadowAnalytics, useShadowBenchmarks, useShadowPromotions, useTournamentRankings, useAllAllocations, useSimulator, useAutoPromotions, useResearchRegistry, useResearchChampion, useResearchHealth, usePortfolioReport, useResearchSignals, useResearchConsensus, useResearchAgentHealth, useResearchRegistryStats, useResearchStatus, useEvolutionPopulation, useEvolutionLineage, useEvolutionCandidates, useEvolutionGenerations, useEvolutionRuns, useGovernanceDecisions, useGovernancePromotions, useGovernanceRetirements, useGovernanceAllocations, useGovernanceRecords, usePortfolioRecommendation, usePortfolioAllocationPlan, usePortfolioIntelligence, useResilience, useStressTests, useCommittee, usePortfolioReviews, useOptimizationPortfolio, useOptimizationSimulation, useOptimizationRisk, useOptimizationExpectedReturns, useControlPortfolioState, useControlPortfolioDrift, useControlPortfolioStability } from "@/lib/hooks";
import { StatCard } from "@/components/StatCard";
import { formatPnl, formatNumber } from "@/lib/utils";
import { Activity, Gauge, TrendingUp, BarChart3, Zap, DollarSign, AlertTriangle, Shield, Target, Award, Trophy, PieChart, TrendingDown, BookOpen, Swords, Heart, FileText, Microscope, GitCompare, Cpu, GitFork, Dna, Scale, Landmark, ClipboardCheck, Building2, Brain, Waves, FlaskConical, ShieldCheck, ClipboardList, SlidersHorizontal } from "lucide-react";
import { useState, useCallback } from "react";
import { api } from "@/lib/api";

type Tab = "overview" | "executions" | "strategies" | "analytics" | "promotion" | "rankings" | "allocations" | "simulator" | "registry" | "champions" | "health" | "reports" | "signals" | "consensus" | "agents" | "evolution" | "population" | "lineage" | "lifecycle" | "allocation-plan" | "governance" | "portfolio-manager" | "portfolio-intelligence" | "regime-allocation" | "stress-tests" | "investment-committee" | "portfolio-optimization" | "portfolio-control";

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
  const { data: evolutionPop, loading: evoPopLoading, refetch: refetchEvoPop } = useEvolutionPopulation();
  const { data: evolutionLineage, loading: evoLineageLoading, refetch: refetchEvoLineage } = useEvolutionLineage();
  const { data: evolutionCandidates, loading: evoCandidatesLoading, refetch: refetchEvoCandidates } = useEvolutionCandidates();
  const { data: evolutionGenerations, loading: evoGenLoading } = useEvolutionGenerations();
  const { data: evolutionRuns, loading: evoRunsLoading, refetch: refetchEvoRuns } = useEvolutionRuns();
  const { data: govDecisions, loading: govDecisionsLoading } = useGovernanceDecisions();
  const { data: govPromotions, loading: govPromotionsLoading } = useGovernancePromotions();
  const { data: govRetirements, loading: govRetirementsLoading } = useGovernanceRetirements();
  const { data: govAllocations, loading: govAllocationsLoading } = useGovernanceAllocations();
  const { data: govRecords, loading: govRecordsLoading } = useGovernanceRecords();
  const { data: portfolioRec, loading: portfolioRecLoading, refetch: refetchPortfolioRec } = usePortfolioRecommendation();
  const { data: allocationPlan, loading: allocationPlanLoading } = usePortfolioAllocationPlan();
  const { data: intelData, loading: intelLoading } = usePortfolioIntelligence();
  const { data: resilienceData, loading: resilienceLoading } = useResilience();
  const { data: stressData, loading: stressLoading } = useStressTests();
  const { data: committeeData, loading: committeeLoading } = useCommittee();
  const { data: reviewsData, loading: reviewsLoading, refetch: refetchReviews } = usePortfolioReviews();
  const { data: optPortfolio, loading: optPortfolioLoading, refetch: refetchOptPortfolio } = useOptimizationPortfolio();
  const { data: optSimulation, loading: optSimulationLoading, refetch: refetchOptSimulation } = useOptimizationSimulation();
  const { data: optRisk, loading: optRiskLoading, refetch: refetchOptRisk } = useOptimizationRisk();
  const { data: optExpectedReturns, loading: optExpectedReturnsLoading, refetch: refetchOptExpectedReturns } = useOptimizationExpectedReturns();
  const { data: ctrlState, loading: ctrlStateLoading, refetch: refetchCtrlState } = useControlPortfolioState();
  const { data: ctrlDrift, loading: ctrlDriftLoading, refetch: refetchCtrlDrift } = useControlPortfolioDrift();
  const { data: ctrlStability, loading: ctrlStabilityLoading } = useControlPortfolioStability();

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

  const handleRunEvolution = async () => {
    try {
      await api.evolution.run();
      refetchEvoPop();
      refetchEvoLineage();
      refetchEvoCandidates();
      refetchEvoRuns();
    } catch (e) {
      console.error("Evolution run failed", e);
    }
  };

  const handleRunPortfolioManager = async () => {
    try {
      await api.portfolioManager.run();
      refetchPortfolioRec();
    } catch (e) {
      console.error("Portfolio manager run failed", e);
    }
  };

  const handleRunOptimization = async () => {
    try {
      await api.optimization.run();
      refetchOptPortfolio();
      refetchOptSimulation();
      refetchOptRisk();
      refetchOptExpectedReturns();
    } catch (e) {
      console.error("Optimization run failed", e);
    }
  };

  const handleRunControlPortfolio = async () => {
    try {
      await api.controlPortfolio.run();
      refetchCtrlState();
      refetchCtrlDrift();
    } catch (e) {
      console.error("Control portfolio run failed", e);
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
    { key: "evolution", label: "Evolution", icon: <Dna className="h-3 w-3" /> },
    { key: "population", label: "Population", icon: <GitFork className="h-3 w-3" /> },
    { key: "lineage", label: "Lineage", icon: <GitCompare className="h-3 w-3" /> },
    { key: "lifecycle", label: "Lifecycle", icon: <Scale className="h-3 w-3" /> },
    { key: "allocation-plan", label: "Allocation", icon: <Landmark className="h-3 w-3" /> },
    { key: "governance", label: "Governance", icon: <ClipboardCheck className="h-3 w-3" /> },
    { key: "portfolio-manager", label: "Portfolio", icon: <Building2 className="h-3 w-3" /> },
    { key: "portfolio-intelligence", label: "Intelligence", icon: <Brain className="h-3 w-3" /> },
    { key: "regime-allocation", label: "Regime Alloc", icon: <Waves className="h-3 w-3" /> },
    { key: "stress-tests", label: "Stress Tests", icon: <FlaskConical className="h-3 w-3" /> },
    { key: "investment-committee", label: "Committee", icon: <ClipboardList className="h-3 w-3" /> },
    { key: "portfolio-optimization", label: "Optimization", icon: <SlidersHorizontal className="h-3 w-3" /> },
    { key: "portfolio-control", label: "Control", icon: <ShieldCheck className="h-3 w-3" /> },
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

      {/* ── Evolution Tab ───────────────────────── */}
      {tab === "evolution" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">
              <Dna className="h-3.5 w-3.5 inline mr-1" />
              Evolution Engine
            </h2>
            <button
              onClick={handleRunEvolution}
              className="text-[10px] px-3 py-1.5 border border-border rounded hover:border-gray-500 transition-colors"
            >
              Run Evolution
            </button>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard title="Candidates" value={`${evolutionCandidates?.candidates?.length ?? 0}`} icon={Dna} loading={evoCandidatesLoading} />
            <StatCard title="Generations" value={`${evolutionGenerations?.generations?.length ?? 0}`} icon={GitFork} loading={evoGenLoading} />
            <StatCard title="Runs" value={`${evolutionRuns?.runs?.length ?? 0}`} icon={Activity} loading={evoRunsLoading} />
            <StatCard title="Population" value={`${evolutionPop?.population?.length ?? 0}`} icon={BarChart3} loading={evoPopLoading} />
          </div>

          {/* Evolution runs table */}
          {evoRunsLoading && <div className="text-center py-4 text-xs text-muted-foreground">Loading runs...</div>}
          {!evoRunsLoading && evolutionRuns?.runs && evolutionRuns.runs.length > 0 && (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
              <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">Evolution Runs</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-gray-800 text-[10px] text-gray-500 uppercase tracking-wider">
                      <th className="text-left py-2 pr-2">Run ID</th>
                      <th className="text-right py-2 pr-2">Candidates</th>
                      <th className="text-right py-2 pr-2">Mutations</th>
                      <th className="text-right py-2 pr-2">Crossovers</th>
                      <th className="text-right py-2 pr-2">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {evolutionRuns.runs.map((run: any, i: number) => (
                      <tr key={run.run_id || i} className="border-b border-gray-900 hover:bg-gray-900/30">
                        <td className="py-2 pr-2 text-gray-300 font-mono">{run.run_id}</td>
                        <td className="py-2 pr-2 text-right font-mono text-gray-300">{run.candidates_created ?? 0}</td>
                        <td className="py-2 pr-2 text-right font-mono text-gray-300">{run.mutations_performed ?? 0}</td>
                        <td className="py-2 pr-2 text-right font-mono text-gray-300">{run.crossovers_performed ?? 0}</td>
                        <td className="py-2 text-right">
                          <span className={`text-[10px] px-1.5 py-0.5 rounded ${run.status === "completed" ? "bg-emerald-500/10 text-emerald-400" : "bg-amber-500/10 text-amber-400"}`}>
                            {(run.status || "").toUpperCase()}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Candidates list */}
          {evoCandidatesLoading && <div className="text-center py-4 text-xs text-muted-foreground">Loading candidates...</div>}
          {!evoCandidatesLoading && evolutionCandidates?.candidates && evolutionCandidates.candidates.length > 0 && (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
              <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">Active Candidates</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-gray-800 text-[10px] text-gray-500 uppercase tracking-wider">
                      <th className="text-left py-2 pr-2">ID</th>
                      <th className="text-left py-2 pr-2">Archetype</th>
                      <th className="text-right py-2 pr-2">Generation</th>
                      <th className="text-right py-2 pr-2">Confidence</th>
                      <th className="text-right py-2 pr-2">Sizing</th>
                      <th className="text-right py-2 pr-2">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {evolutionCandidates.candidates.map((c: any, i: number) => (
                      <tr key={c.candidate_id || i} className="border-b border-gray-900 hover:bg-gray-900/30">
                        <td className="py-2 pr-2 text-gray-300 font-mono text-[10px]">{(c.candidate_id || "").slice(0, 12)}</td>
                        <td className="py-2 pr-2 text-gray-300">{(c.genome?.archetype || "-")}</td>
                        <td className="py-2 pr-2 text-right font-mono text-gray-300">{c.genome?.generation ?? 0}</td>
                        <td className="py-2 pr-2 text-right font-mono text-gray-300">{c.genome?.confidence_threshold?.toFixed(2) ?? "-"}</td>
                        <td className="py-2 pr-2 text-right font-mono text-gray-300">{c.genome?.sizing_multiplier?.toFixed(2) ?? "-"}</td>
                        <td className="py-2 text-right">
                          <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                            c.status === "EXPERIMENTAL" ? "bg-blue-500/10 text-blue-400" :
                            c.status === "SHADOW" ? "bg-purple-500/10 text-purple-400" :
                            c.status === "LIVE" ? "bg-emerald-500/10 text-emerald-400" :
                            c.status === "RETIRED" ? "bg-gray-500/10 text-gray-400" :
                            "bg-amber-500/10 text-amber-400"
                          }`}>
                            {c.status || "UNKNOWN"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Population Tab ──────────────────────── */}
      {tab === "population" && (
        <div className="space-y-4">
          <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">
            <GitFork className="h-3.5 w-3.5 inline mr-1" />
            Population
          </h2>

          {evoPopLoading && <div className="text-center py-8 text-xs text-muted-foreground">Loading population...</div>}
          {!evoPopLoading && evolutionPop?.population && evolutionPop.population.length > 0 && (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
              <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">Fitness Leaderboard</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-gray-800 text-[10px] text-gray-500 uppercase tracking-wider">
                      <th className="text-left py-2 pr-2">Rank</th>
                      <th className="text-left py-2 pr-2">Strategy ID</th>
                      <th className="text-right py-2 pr-2">Gen</th>
                      <th className="text-left py-2 pr-2">Archetype</th>
                      <th className="text-right py-2 pr-2">Fitness</th>
                      <th className="text-left py-2">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...evolutionPop.population]
                      .sort((a: any, b: any) => (b.fitness ?? 0) - (a.fitness ?? 0))
                      .map((entry: any, i: number) => (
                      <tr key={entry.strategy_id || i} className="border-b border-gray-900 hover:bg-gray-900/30">
                        <td className="py-2 pr-2 text-gray-500 font-mono">{i + 1}</td>
                        <td className="py-2 pr-2 text-gray-300 font-mono text-[10px]">{(entry.strategy_id || "").slice(0, 12)}</td>
                        <td className="py-2 pr-2 text-right font-mono text-gray-300">{entry.generation ?? 0}</td>
                        <td className="py-2 pr-2 text-gray-300">{entry.archetype || "-"}</td>
                        <td className="py-2 pr-2 text-right font-mono text-gray-300">{entry.fitness?.toFixed(1) ?? "-"}</td>
                        <td className="py-2">
                          <span className={`text-[10px] px-1.5 py-0.5 rounded ${entry.status === "active" ? "bg-emerald-500/10 text-emerald-400" : "bg-gray-500/10 text-gray-400"}`}>
                            {(entry.status || "").toUpperCase()}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Generation statistics */}
          {!evoGenLoading && evolutionGenerations?.generations && evolutionGenerations.generations.length > 0 && (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
              <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">Generation History</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-gray-800 text-[10px] text-gray-500 uppercase tracking-wider">
                      <th className="text-left py-2 pr-2">Run ID</th>
                      <th className="text-right py-2 pr-2">Candidates</th>
                      <th className="text-right py-2 pr-2">Mutations</th>
                      <th className="text-right py-2">Crossovers</th>
                    </tr>
                  </thead>
                  <tbody>
                    {evolutionGenerations.generations.map((g: any, i: number) => (
                      <tr key={g.run_id || i} className="border-b border-gray-900 hover:bg-gray-900/30">
                        <td className="py-2 pr-2 text-gray-300 font-mono text-[10px]">{(g.run_id || "").slice(0, 16)}</td>
                        <td className="py-2 pr-2 text-right font-mono text-gray-300">{g.candidates_created ?? g.candidates ?? 0}</td>
                        <td className="py-2 pr-2 text-right font-mono text-gray-300">{g.mutations ?? g.mutations_performed ?? 0}</td>
                        <td className="py-2 text-right font-mono text-gray-300">{g.crossovers ?? g.crossovers_performed ?? 0}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {!evoPopLoading && (!evolutionPop?.population || evolutionPop.population.length === 0) && (
            <div className="text-center py-8 text-xs text-muted-foreground">No population data available.</div>
          )}
        </div>
      )}

      {/* ── Lineage Tab ─────────────────────────── */}
      {tab === "lineage" && (
        <div className="space-y-4">
          <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">
            <GitCompare className="h-3.5 w-3.5 inline mr-1" />
            Strategy Lineage
          </h2>

          {evoLineageLoading && <div className="text-center py-8 text-xs text-muted-foreground">Loading lineage...</div>}
          {!evoLineageLoading && evolutionLineage?.lineage && evolutionLineage.lineage.length > 0 && (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
              <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">Lineage Tree</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-gray-800 text-[10px] text-gray-500 uppercase tracking-wider">
                      <th className="text-left py-2 pr-2">Strategy ID</th>
                      <th className="text-right py-2 pr-2">Gen</th>
                      <th className="text-left py-2 pr-2">Archetype</th>
                      <th className="text-left py-2 pr-2">Parents</th>
                      <th className="text-right py-2 pr-2">Fitness</th>
                      <th className="text-left py-2">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {evolutionLineage.lineage.map((node: any, i: number) => (
                      <tr key={node.strategy_id || i} className="border-b border-gray-900 hover:bg-gray-900/30">
                        <td className="py-2 pr-2 text-gray-300 font-mono text-[10px]">{(node.strategy_id || "").slice(0, 12)}</td>
                        <td className="py-2 pr-2 text-right font-mono text-gray-300">{node.generation ?? 0}</td>
                        <td className="py-2 pr-2 text-gray-300">{node.archetype || "-"}</td>
                        <td className="py-2 pr-2 text-gray-500 text-[10px]">{(node.parent_ids || []).length > 0 ? node.parent_ids.map((p: string) => p.slice(0, 8)).join(", ") : "-"}</td>
                        <td className="py-2 pr-2 text-right font-mono text-gray-300">{node.fitness?.toFixed(1) ?? "-"}</td>
                        <td className="py-2">
                          <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                            node.status === "LIVE" ? "bg-emerald-500/10 text-emerald-400" :
                            node.status === "SHADOW" ? "bg-purple-500/10 text-purple-400" :
                            node.status === "RETIRED" ? "bg-gray-500/10 text-gray-400" :
                            node.status === "active" ? "bg-blue-500/10 text-blue-400" :
                            "bg-amber-500/10 text-amber-400"
                          }`}>
                            {(node.status || "").toUpperCase()}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Promotion history summary */}
          {!evoLineageLoading && evolutionLineage?.lineage && evolutionLineage.lineage.length > 0 && (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
              <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">Promotion History</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="text-center p-3 bg-emerald-500/5 rounded-lg">
                  <div className="text-lg font-bold text-emerald-400">
                    {evolutionLineage.lineage.filter((n: any) => n.status === "LIVE").length}
                  </div>
                  <div className="text-[10px] text-gray-500">LIVE</div>
                </div>
                <div className="text-center p-3 bg-purple-500/5 rounded-lg">
                  <div className="text-lg font-bold text-purple-400">
                    {evolutionLineage.lineage.filter((n: any) => n.status === "SHADOW").length}
                  </div>
                  <div className="text-[10px] text-gray-500">SHADOW</div>
                </div>
                <div className="text-center p-3 bg-gray-500/5 rounded-lg">
                  <div className="text-lg font-bold text-gray-400">
                    {evolutionLineage.lineage.filter((n: any) => n.status === "RETIRED").length}
                  </div>
                  <div className="text-[10px] text-gray-500">RETIRED</div>
                </div>
              </div>
            </div>
          )}

          {!evoLineageLoading && (!evolutionLineage?.lineage || evolutionLineage.lineage.length === 0) && (
            <div className="text-center py-8 text-xs text-muted-foreground">No lineage data available.</div>
          )}
        </div>
      )}

      {/* ── Lifecycle Tab ────────────────────────── */}
      {tab === "lifecycle" && (
        <div className="space-y-4">
          <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">
            <Scale className="h-3.5 w-3.5 inline mr-1" />
            Strategy Lifecycle
          </h2>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard title="Promotion Candidates" value={`${govPromotions?.promotions?.length ?? 0}`} icon={TrendingUp} loading={govPromotionsLoading} />
            <StatCard title="Retirement Candidates" value={`${govRetirements?.retirements?.length ?? 0}`} icon={AlertTriangle} loading={govRetirementsLoading} color={(govRetirements?.retirements?.length ?? 0) > 0 ? "negative" : "default"} />
            <StatCard title="Decisions Made" value={`${govDecisions?.decisions?.length ?? 0}`} icon={ClipboardCheck} loading={govDecisionsLoading} />
            <StatCard title="Governance Records" value={`${govRecords?.records?.length ?? 0}`} icon={FileText} loading={govRecordsLoading} />
          </div>

          {govPromotionsLoading && <div className="text-center py-4 text-xs text-muted-foreground">Loading promotions...</div>}
          {!govPromotionsLoading && govPromotions?.promotions && govPromotions.promotions.length > 0 && (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
              <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">Promotion Candidates</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-gray-800 text-[10px] text-gray-500 uppercase tracking-wider">
                      <th className="text-left py-2 pr-2">Strategy</th>
                      <th className="text-left py-2 pr-2">From</th>
                      <th className="text-left py-2 pr-2">To</th>
                      <th className="text-right py-2 pr-2">Score</th>
                      <th className="text-left py-2">Source</th>
                    </tr>
                  </thead>
                  <tbody>
                    {govPromotions.promotions.map((p: any, i: number) => (
                      <tr key={p.strategy_id || i} className="border-b border-gray-900 hover:bg-gray-900/30">
                        <td className="py-2 pr-2 text-gray-300 font-mono text-[10px]">{(p.strategy_id || "").slice(0, 14)}</td>
                        <td className="py-2 pr-2 text-gray-300">{p.current_tier || "-"}</td>
                        <td className="py-2 pr-2 text-emerald-400 font-medium">{p.recommended_tier || "-"}</td>
                        <td className="py-2 pr-2 text-right font-mono text-gray-300">{p.score ?? "-"}</td>
                        <td className="py-2 text-[10px] text-gray-500">{p.source || "auto"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {govRetirementsLoading && <div className="text-center py-4 text-xs text-muted-foreground">Loading retirements...</div>}
          {!govRetirementsLoading && govRetirements?.retirements && govRetirements.retirements.length > 0 && (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
              <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">Retirement Candidates</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-gray-800 text-[10px] text-gray-500 uppercase tracking-wider">
                      <th className="text-left py-2 pr-2">Strategy</th>
                      <th className="text-left py-2 pr-2">Reason</th>
                      <th className="text-right py-2 pr-2">Score</th>
                      <th className="text-left py-2">Triggers</th>
                    </tr>
                  </thead>
                  <tbody>
                    {govRetirements.retirements.map((r: any, i: number) => (
                      <tr key={r.strategy_id || i} className="border-b border-gray-900 hover:bg-gray-900/30">
                        <td className="py-2 pr-2 text-gray-300 font-mono text-[10px]">{(r.strategy_id || "").slice(0, 14)}</td>
                        <td className="py-2 pr-2 text-gray-300 max-w-[200px] truncate">{r.reason || "-"}</td>
                        <td className="py-2 pr-2 text-right font-mono text-red-400">{r.score ?? "-"}</td>
                        <td className="py-2 text-[10px] text-gray-500">{r.triggers?.length ?? 0} triggers</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {!govPromotionsLoading && (!govPromotions?.promotions || govPromotions.promotions.length === 0) && !govRetirementsLoading && (!govRetirements?.retirements || govRetirements.retirements.length === 0) && (
            <div className="text-center py-8 text-xs text-muted-foreground">No lifecycle data available. Run Portfolio Manager to generate recommendations.</div>
          )}
        </div>
      )}

      {/* ── Allocation Tab ──────────────────────── */}
      {tab === "allocation-plan" && (
        <div className="space-y-4">
          <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">
            <Landmark className="h-3.5 w-3.5 inline mr-1" />
            Capital Allocation Plan
          </h2>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard title="Active Allocations" value={`${allocationPlan?.plan?.allocations?.length ?? 0}`} icon={PieChart} loading={allocationPlanLoading || govAllocationsLoading} />
            <StatCard title="Mode" value={allocationPlan?.plan?.mode || "-"} icon={Gauge} loading={allocationPlanLoading || govAllocationsLoading} />
          </div>

          {allocationPlanLoading && <div className="text-center py-4 text-xs text-muted-foreground">Loading allocation plan...</div>}
          {!allocationPlanLoading && allocationPlan?.plan?.allocations && allocationPlan.plan.allocations.length > 0 && (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
              <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">Current Allocation</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-gray-800 text-[10px] text-gray-500 uppercase tracking-wider">
                      <th className="text-left py-2 pr-2">Strategy</th>
                      <th className="text-left py-2 pr-2">Tier</th>
                      <th className="text-right py-2 pr-2">Allocation %</th>
                      <th className="text-right py-2 pr-2">Sharpe</th>
                      <th className="text-right py-2 pr-2">Health</th>
                      <th className="text-right py-2">Rank</th>
                    </tr>
                  </thead>
                  <tbody>
                    {allocationPlan.plan.allocations.map((a: any, i: number) => (
                      <tr key={a.strategy_id || i} className="border-b border-gray-900 hover:bg-gray-900/30">
                        <td className="py-2 pr-2 text-gray-300 font-mono text-[10px]">{(a.strategy_id || "").slice(0, 14)}</td>
                        <td className="py-2 pr-2">
                          <span className={`text-[10px] px-1.5 py-0.5 rounded ${a.tier === "LIVE" ? "bg-emerald-500/10 text-emerald-400" : a.tier === "PAPER" ? "bg-blue-500/10 text-blue-400" : "bg-gray-500/10 text-gray-400"}`}>
                            {a.tier || "-"}
                          </span>
                        </td>
                        <td className="py-2 pr-2 text-right font-mono text-gray-300">{a.allocation_pct?.toFixed(1) ?? "-"}%</td>
                        <td className="py-2 pr-2 text-right font-mono text-gray-300">{a.sharpe?.toFixed(2) ?? "-"}</td>
                        <td className="py-2 pr-2 text-right font-mono text-gray-300">{a.health?.toFixed(0) ?? "-"}</td>
                        <td className="py-2 text-right font-mono text-gray-300">#{a.rank ?? "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Allocation heatmap */}
          {!allocationPlanLoading && allocationPlan?.plan?.allocations && allocationPlan.plan.allocations.length > 0 && (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
              <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">Allocation Heatmap</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2">
                {allocationPlan.plan.allocations.map((a: any, i: number) => {
                  const pct = a.allocation_pct || 0;
                  const intensity = Math.min(1.0, pct / 25.0);
                  const bg = a.tier === "LIVE"
                    ? `rgba(16, 185, 129, ${intensity})`
                    : `rgba(59, 130, 246, ${intensity})`;
                  return (
                    <div key={a.strategy_id || i} className="rounded-lg p-3 text-center" style={{ background: bg }}>
                      <div className="text-[10px] font-mono text-white truncate">{(a.strategy_id || "").slice(0, 10)}</div>
                      <div className="text-lg font-bold text-white">{pct.toFixed(1)}%</div>
                      <div className="text-[10px] text-white/70">{a.tier || "-"}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {!allocationPlanLoading && (!allocationPlan?.plan?.allocations || allocationPlan.plan.allocations.length === 0) && (
            <div className="text-center py-8 text-xs text-muted-foreground">No allocation plan available. Run Portfolio Manager to generate one.</div>
          )}
        </div>
      )}

      {/* ── Governance Tab ──────────────────────── */}
      {tab === "governance" && (
        <div className="space-y-4">
          <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">
            <ClipboardCheck className="h-3.5 w-3.5 inline mr-1" />
            Governance &amp; Explainability
          </h2>

          {govRecordsLoading && <div className="text-center py-4 text-xs text-muted-foreground">Loading governance records...</div>}
          {!govRecordsLoading && govRecords?.records && govRecords.records.length > 0 && (
            <div className="space-y-3">
              {govRecords.records.slice(-20).reverse().map((r: any, i: number) => (
                <div key={r.record_id || i} className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                        r.decision_type === "promotion" ? "bg-emerald-500/10 text-emerald-400" :
                        r.decision_type === "retirement" ? "bg-red-500/10 text-red-400" :
                        r.decision_type === "allocation" ? "bg-blue-500/10 text-blue-400" :
                        "bg-gray-500/10 text-gray-400"
                      }`}>
                        {(r.decision_type || "").toUpperCase()}
                      </span>
                      <span className="text-[10px] font-mono text-gray-500">{(r.strategy_id || "").slice(0, 14)}</span>
                    </div>
                    <span className="text-[9px] text-gray-600">{r.created_at ? new Date(r.created_at).toLocaleString() : ""}</span>
                  </div>
                  <pre className="text-[10px] text-gray-300 whitespace-pre-wrap font-sans leading-relaxed">{r.reasoning || "No reasoning available."}</pre>
                </div>
              ))}
            </div>
          )}

          {!govRecordsLoading && (!govRecords?.records || govRecords.records.length === 0) && (
            <div className="text-center py-8 text-xs text-muted-foreground">No governance records available. Run Portfolio Manager to generate decisions.</div>
          )}
        </div>
      )}

      {/* ── Portfolio Manager Tab ───────────────── */}
      {tab === "portfolio-manager" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">
              <Building2 className="h-3.5 w-3.5 inline mr-1" />
              Portfolio Manager
            </h2>
            <button
              onClick={handleRunPortfolioManager}
              className="text-[10px] px-3 py-1.5 border border-border rounded hover:border-gray-500 transition-colors"
            >
              Run Review
            </button>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard title="Active Strategies" value={`${portfolioRec?.recommendation?.active_strategies?.length ?? 0}`} icon={Target} loading={portfolioRecLoading} />
            <StatCard title="Promotion Candidates" value={`${portfolioRec?.recommendation?.promotion_candidates?.length ?? 0}`} icon={TrendingUp} loading={portfolioRecLoading} />
            <StatCard title="Retirement Candidates" value={`${portfolioRec?.recommendation?.retirement_candidates?.length ?? 0}`} icon={AlertTriangle} loading={portfolioRecLoading} color={(portfolioRec?.recommendation?.retirement_candidates?.length ?? 0) > 0 ? "negative" : "default"} />
            <StatCard title="Allocations" value={`${portfolioRec?.recommendation?.allocation_plan?.allocations?.length ?? 0}`} icon={PieChart} loading={portfolioRecLoading} />
          </div>

          {portfolioRecLoading && <div className="text-center py-4 text-xs text-muted-foreground">Loading portfolio recommendation...</div>}
          {!portfolioRecLoading && portfolioRec?.recommendation?.active_strategies && portfolioRec.recommendation.active_strategies.length > 0 && (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
              <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">Recommended Strategy Set</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-gray-800 text-[10px] text-gray-500 uppercase tracking-wider">
                      <th className="text-left py-2 pr-2">Strategy</th>
                      <th className="text-left py-2 pr-2">Tier</th>
                      <th className="text-right py-2 pr-2">Sharpe</th>
                      <th className="text-right py-2 pr-2">Health</th>
                      <th className="text-right py-2 pr-2">Confidence</th>
                      <th className="text-right py-2">Rank</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(portfolioRec.recommendation.active_strategies || []).map((s: any, i: number) => (
                      <tr key={s.strategy_id || i} className="border-b border-gray-900 hover:bg-gray-900/30">
                        <td className="py-2 pr-2 text-gray-300 font-mono text-[10px]">{(s.strategy_id || "").slice(0, 14)}</td>
                        <td className="py-2 pr-2">
                          <span className={`text-[10px] px-1.5 py-0.5 rounded ${s.tier === "LIVE" ? "bg-emerald-500/10 text-emerald-400" : s.tier === "PAPER" ? "bg-blue-500/10 text-blue-400" : "bg-gray-500/10 text-gray-400"}`}>
                            {s.tier || "-"}
                          </span>
                        </td>
                        <td className="py-2 pr-2 text-right font-mono text-gray-300">{s.sharpe?.toFixed(2) ?? "-"}</td>
                        <td className="py-2 pr-2 text-right font-mono text-gray-300">{s.health?.toFixed(0) ?? "-"}</td>
                        <td className="py-2 pr-2 text-right font-mono text-gray-300">{s.confidence?.toFixed(2) ?? "-"}</td>
                        <td className="py-2 text-right font-mono text-gray-300">#{s.rank ?? "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Recommended capital split */}
          {!portfolioRecLoading && portfolioRec?.recommendation?.allocation_plan?.allocations && portfolioRec.recommendation.allocation_plan.allocations.length > 0 && (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
              <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">Recommended Capital Split</h3>
              <div className="space-y-2">
                {portfolioRec.recommendation.allocation_plan.allocations.map((a: any, i: number) => {
                  const pct = a.allocation_pct || 0;
                  return (
                    <div key={a.strategy_id || i} className="flex items-center gap-3">
                      <span className="text-[10px] font-mono text-gray-300 w-24 truncate">{(a.strategy_id || "").slice(0, 14)}</span>
                      <div className="flex-1 h-4 bg-gray-800 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{
                            width: `${pct}%`,
                            background: a.tier === "LIVE"
                              ? "linear-gradient(90deg, #10b981, #34d399)"
                              : "linear-gradient(90deg, #3b82f6, #60a5fa)",
                          }}
                        />
                      </div>
                      <span className="text-[10px] font-mono text-gray-300 w-16 text-right">{pct.toFixed(1)}%</span>
                      <span className={`text-[9px] px-1.5 py-0.5 rounded ${a.tier === "LIVE" ? "bg-emerald-500/10 text-emerald-400" : "bg-blue-500/10 text-blue-400"}`}>
                        {a.tier || "-"}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Strategy tiers */}
          {!portfolioRecLoading && portfolioRec?.recommendation?.active_strategies && portfolioRec.recommendation.active_strategies.length > 0 && (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
              <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">Confidence &amp; Health Summary</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="text-center p-3 bg-emerald-500/5 rounded-lg">
                  <div className="text-lg font-bold text-emerald-400">
                    {portfolioRec.recommendation.active_strategies.filter((s: any) => s.tier === "LIVE").length}
                  </div>
                  <div className="text-[10px] text-gray-500">LIVE Strategies</div>
                </div>
                <div className="text-center p-3 bg-blue-500/5 rounded-lg">
                  <div className="text-lg font-bold text-blue-400">
                    {portfolioRec.recommendation.active_strategies.filter((s: any) => s.tier === "PAPER").length}
                  </div>
                  <div className="text-[10px] text-gray-500">PAPER Strategies</div>
                </div>
                <div className="text-center p-3 bg-gray-500/5 rounded-lg">
                  <div className="text-lg font-bold text-gray-400">
                    {portfolioRec.recommendation.active_strategies.length}
                  </div>
                  <div className="text-[10px] text-gray-500">Total Active</div>
                </div>
              </div>
            </div>
          )}

          {!portfolioRecLoading && (!portfolioRec?.recommendation || !portfolioRec.recommendation.active_strategies || portfolioRec.recommendation.active_strategies.length === 0) && (
            <div className="text-center py-8 text-xs text-muted-foreground">No portfolio recommendation available. Click "Run Review" to generate one.</div>
          )}
        </div>
      )}

      {tab === "portfolio-intelligence" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">
              <Brain className="h-3.5 w-3.5 inline mr-1" />
              Portfolio Intelligence
            </h2>
            <button
              onClick={async () => { await api.intelligence.runReview(); refetchReviews(); }}
              className="text-[10px] px-3 py-1.5 border border-border rounded hover:border-gray-500 transition-colors"
            >
              Run Review
            </button>
          </div>

          {intelLoading && <div className="text-center py-8 text-xs text-muted-foreground">Loading intelligence...</div>}
          {!intelLoading && intelData?.latest && (
            <>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 text-center">
                  <div className={`text-xl font-bold font-mono ${(intelData.latest.quality_score || 0) >= 60 ? "text-emerald-400" : (intelData.latest.quality_score || 0) >= 40 ? "text-amber-400" : "text-red-400"}`}>
                    {(intelData.latest.quality_score || 0).toFixed(1)}
                  </div>
                  <div className="text-[10px] text-gray-500 mt-1">Quality Score</div>
                </div>
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 text-center">
                  <div className={`text-xl font-bold font-mono ${(intelData.latest.diversification_score || 0) >= 60 ? "text-emerald-400" : "text-amber-400"}`}>
                    {(intelData.latest.diversification_score || 0).toFixed(1)}
                  </div>
                  <div className="text-[10px] text-gray-500 mt-1">Diversification</div>
                </div>
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 text-center">
                  <div className={`text-xl font-bold font-mono ${(intelData.latest.concentration_score || 0) <= 40 ? "text-emerald-400" : (intelData.latest.concentration_score || 0) <= 60 ? "text-amber-400" : "text-red-400"}`}>
                    {(intelData.latest.concentration_score || 0).toFixed(1)}
                  </div>
                  <div className="text-[10px] text-gray-500 mt-1">Concentration</div>
                </div>
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 text-center">
                  <div className={`text-xl font-bold font-mono ${(intelData.latest.regime_fitness_score || 0) >= 60 ? "text-emerald-400" : "text-amber-400"}`}>
                    {(intelData.latest.regime_fitness_score || 0).toFixed(1)}
                  </div>
                  <div className="text-[10px] text-gray-500 mt-1">Regime Fitness</div>
                </div>
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 text-center">
                  <div className={`text-xl font-bold font-mono ${(intelData.latest.strategy_overlap_score || 0) >= 60 ? "text-emerald-400" : "text-amber-400"}`}>
                    {(intelData.latest.strategy_overlap_score || 0).toFixed(1)}
                  </div>
                  <div className="text-[10px] text-gray-500 mt-1">Strategy Overlap</div>
                </div>
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 text-center">
                  <div className={`text-xl font-bold font-mono ${(intelData.latest.capital_efficiency_score || 0) >= 60 ? "text-emerald-400" : "text-amber-400"}`}>
                    {(intelData.latest.capital_efficiency_score || 0).toFixed(1)}
                  </div>
                  <div className="text-[10px] text-gray-500 mt-1">Capital Efficiency</div>
                </div>
              </div>

              {intelData.history && intelData.history.length > 1 && (
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                  <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">History</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-gray-800 text-[10px] text-gray-500 uppercase tracking-wider">
                          <th className="text-left py-2 pr-2">Time</th>
                          <th className="text-right py-2 pr-2">Quality</th>
                          <th className="text-right py-2 pr-2">Div.</th>
                          <th className="text-right py-2 pr-2">Conc.</th>
                          <th className="text-right py-2 pr-2">Regime Fit</th>
                          <th className="text-right py-2 pr-2">Overlap</th>
                          <th className="text-right py-2">Efficiency</th>
                        </tr>
                      </thead>
                      <tbody>
                        {intelData.history.slice(-10).reverse().map((r: any, i: number) => (
                          <tr key={i} className="border-b border-gray-900 hover:bg-gray-900/30">
                            <td className="py-2 pr-2 text-gray-500 text-[10px]">{(r.generated_at || "").slice(11, 19)}</td>
                            <td className="py-2 pr-2 text-right font-mono">{r.quality_score?.toFixed(1)}</td>
                            <td className="py-2 pr-2 text-right font-mono">{r.diversification_score?.toFixed(1)}</td>
                            <td className="py-2 pr-2 text-right font-mono">{r.concentration_score?.toFixed(1)}</td>
                            <td className="py-2 pr-2 text-right font-mono">{r.regime_fitness_score?.toFixed(1)}</td>
                            <td className="py-2 pr-2 text-right font-mono">{r.strategy_overlap_score?.toFixed(1)}</td>
                            <td className="py-2 text-right font-mono">{r.capital_efficiency_score?.toFixed(1)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          )}
          {!intelLoading && !intelData?.latest && (
            <div className="text-center py-8 text-xs text-muted-foreground">No intelligence data yet. Run a review to generate.</div>
          )}
        </div>
      )}

      {tab === "regime-allocation" && (
        <div className="space-y-4">
          <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">
            <Waves className="h-3.5 w-3.5 inline mr-1" />
            Regime Allocation
          </h2>

          {intelLoading && <div className="text-center py-8 text-xs text-muted-foreground">Loading...</div>}
          {!intelLoading && intelData?.latest && (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                <div className="text-center p-3 rounded-lg border border-gray-800">
                  <div className="text-lg font-bold font-mono text-white">{intelData.latest.regime_fitness_score?.toFixed(1) || "-"}</div>
                  <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Regime Fitness</div>
                </div>
                <div className="text-center p-3 rounded-lg border border-gray-800">
                  <div className="text-lg font-bold font-mono text-white">{intelData.latest.diversification_score?.toFixed(1) || "-"}</div>
                  <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Diversification</div>
                </div>
                <div className="text-center p-3 rounded-lg border border-gray-800">
                  <div className="text-lg font-bold font-mono text-white">{intelData.latest.concentration_score?.toFixed(1) || "-"}</div>
                  <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Concentration</div>
                </div>
                <div className="text-center p-3 rounded-lg border border-gray-800">
                  <div className="text-lg font-bold font-mono text-white">{intelData.latest.quality_score?.toFixed(1) || "-"}</div>
                  <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Quality Score</div>
                </div>
              </div>
            </div>
          )}
          {!intelLoading && !intelData?.latest && (
            <div className="text-center py-8 text-xs text-muted-foreground">Run a portfolio review to see regime allocation.</div>
          )}
        </div>
      )}

      {tab === "stress-tests" && (
        <div className="space-y-4">
          <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">
            <FlaskConical className="h-3.5 w-3.5 inline mr-1" />
            Stress Tests
          </h2>
          {stressLoading && <div className="text-center py-8 text-xs text-muted-foreground">Loading stress tests...</div>}
          {!stressLoading && stressData?.results && stressData.results.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {stressData.results.map((r: any, i: number) => (
                <div key={i} className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-xs font-bold text-white capitalize">{r.scenario_type?.replace(/_/g, " ")}</h3>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${r.resilience_score >= 50 ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"}`}>
                      Resilience: {r.resilience_score?.toFixed(0)}
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    <div className="text-center p-2 rounded border border-gray-800">
                      <div className={`text-sm font-bold font-mono ${r.expected_drawdown >= 0.3 ? "text-red-400" : "text-amber-400"}`}>
                        {(r.expected_drawdown * 100).toFixed(1)}%
                      </div>
                      <div className="text-[9px] text-muted-foreground">Drawdown</div>
                    </div>
                    <div className="text-center p-2 rounded border border-gray-800">
                      <div className="text-sm font-bold font-mono text-white">{r.recovery_time_hours?.toFixed(0)}h</div>
                      <div className="text-[9px] text-muted-foreground">Recovery</div>
                    </div>
                    <div className="text-center p-2 rounded border border-gray-800">
                      <div className={`text-sm font-bold font-mono ${r.resilience_score >= 50 ? "text-emerald-400" : "text-red-400"}`}>
                        {r.resilience_score?.toFixed(0)}
                      </div>
                      <div className="text-[9px] text-muted-foreground">Score</div>
                    </div>
                  </div>
                  {r.strategy_survivability && Object.keys(r.strategy_survivability).length > 0 && (
                    <div className="mt-3">
                      <div className="text-[10px] text-gray-500 mb-2">Strategy Survivability</div>
                      {Object.entries(r.strategy_survivability).slice(0, 5).map(([sid, surv]: [string, any]) => (
                        <div key={sid} className="flex items-center gap-2 py-1">
                          <span className="text-[10px] font-mono text-gray-300 w-20 truncate">{sid.slice(0, 10)}</span>
                          <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
                            <div className={`h-full rounded-full ${surv >= 50 ? "bg-emerald-500" : "bg-red-500"}`} style={{ width: `${surv}%` }} />
                          </div>
                          <span className="text-[10px] font-mono text-gray-400 w-8 text-right">{surv.toFixed(0)}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
          {!stressLoading && (!stressData?.results || stressData.results.length === 0) && (
            <div className="text-center py-8 text-xs text-muted-foreground">No stress test results yet. Run a portfolio review.</div>
          )}
        </div>
      )}

      {tab === "investment-committee" && (
        <div className="space-y-4">
          <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">
            <ClipboardList className="h-3.5 w-3.5 inline mr-1" />
            Investment Committee
          </h2>
          {committeeLoading && <div className="text-center py-8 text-xs text-muted-foreground">Loading committee report...</div>}
          {!committeeLoading && committeeData?.latest && (
            <>
              <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-2">Summary</h3>
                <p className="text-xs text-gray-300">{committeeData.latest.summary || "No summary available."}</p>
              </div>

              {committeeData.latest.recommendations && committeeData.latest.recommendations.length > 0 && (
                <div className="space-y-3">
                  {committeeData.latest.recommendations.map((rec: any, i: number) => (
                    <div key={i} className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                            rec.recommendation_type === "increase_allocation" ? "bg-emerald-500/10 text-emerald-400" :
                            rec.recommendation_type === "retire_strategy" ? "bg-red-500/10 text-red-400" :
                            rec.recommendation_type === "incubate_candidate" ? "bg-blue-500/10 text-blue-400" :
                            "bg-amber-500/10 text-amber-400"
                          }`}>
                            {rec.recommendation_type?.replace(/_/g, " ")}
                          </span>
                          <span className="text-xs text-white font-mono">{rec.target}</span>
                        </div>
                        <span className={`text-[10px] font-mono ${rec.confidence >= 0.7 ? "text-emerald-400" : rec.confidence >= 0.5 ? "text-amber-400" : "text-gray-400"}`}>
                          {(rec.confidence * 100).toFixed(0)}% confidence
                        </span>
                      </div>
                      <p className="text-[11px] text-gray-400">{rec.rationale}</p>
                      {rec.supporting_metrics && Object.keys(rec.supporting_metrics).length > 0 && (
                        <div className="mt-2 flex gap-2 flex-wrap">
                          {Object.entries(rec.supporting_metrics).map(([k, v]: [string, any]) => (
                            <span key={k} className="text-[9px] text-gray-600 bg-gray-800 px-1.5 py-0.5 rounded">
                              {k}: {typeof v === "number" ? v.toFixed(2) : v}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
          {!committeeLoading && !committeeData?.latest && (
            <div className="text-center py-8 text-xs text-muted-foreground">No committee report yet. Run a portfolio review to generate recommendations.</div>
          )}
        </div>
      )}

      {/* ── Portfolio Control Tab ────────────────── */}
      {tab === "portfolio-control" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">
              <ShieldCheck className="h-3.5 w-3.5 inline mr-1" />
              Portfolio Control System
            </h2>
            <button
              onClick={handleRunControlPortfolio}
              className="text-[10px] px-3 py-1.5 border border-border rounded hover:border-gray-500 transition-colors"
            >
              Run Control Cycle
            </button>
          </div>

          {/* A. Stability Overview */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
            <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
              <Shield className="h-3 w-3 inline mr-1" />
              Stability Overview
            </h3>
            {ctrlStabilityLoading && <div className="text-center py-4 text-xs text-muted-foreground">Loading...</div>}
            {!ctrlStabilityLoading && ctrlStability && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="text-center p-3 rounded-lg border border-gray-800">
                  <div className={`text-lg font-bold font-mono ${(ctrlStability.allocation_stability || 0) >= 80 ? "text-emerald-400" : (ctrlStability.allocation_stability || 0) >= 50 ? "text-amber-400" : "text-red-400"}`}>
                    {(ctrlStability.allocation_stability || 0).toFixed(1)}
                  </div>
                  <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Allocation Stability</div>
                </div>
                <div className="text-center p-3 rounded-lg border border-gray-800">
                  <div className={`text-lg font-bold font-mono ${(ctrlStability.turnover_rate || 0) <= 0.2 ? "text-emerald-400" : (ctrlStability.turnover_rate || 0) <= 0.4 ? "text-amber-400" : "text-red-400"}`}>
                    {((ctrlStability.turnover_rate || 0) * 100).toFixed(1)}%
                  </div>
                  <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Turnover Rate</div>
                </div>
                <div className="text-center p-3 rounded-lg border border-gray-800">
                  <div className={`text-lg font-bold font-mono ${(ctrlStability.drift_index || 0) <= 20 ? "text-emerald-400" : (ctrlStability.drift_index || 0) <= 50 ? "text-amber-400" : "text-red-400"}`}>
                    {ctrlStability.drift_index ?? "-"}
                  </div>
                  <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Drift Index</div>
                </div>
                <div className="text-center p-3 rounded-lg border border-gray-800">
                  <div className={`text-lg font-bold font-mono ${ctrlStability.regime_stability ? "text-emerald-400" : "text-amber-400"}`}>
                    {ctrlStability.regime_stability ? "Stable" : "Adjusting"}
                  </div>
                  <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Regime Stability</div>
                </div>
              </div>
            )}
            {!ctrlStabilityLoading && !ctrlStability && (
              <div className="text-center py-4 text-xs text-muted-foreground">No stability data available.</div>
            )}
          </div>

          {/* B. Drift Analysis */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
            <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
              <AlertTriangle className="h-3 w-3 inline mr-1" />
              Drift Analysis
            </h3>
            {ctrlDriftLoading && <div className="text-center py-4 text-xs text-muted-foreground">Loading...</div>}
            {!ctrlDriftLoading && ctrlDrift && (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                  <div className="text-center p-3 rounded-lg border border-gray-800">
                    <div className={`text-lg font-bold font-mono ${(ctrlDrift.overall_drift_score || 0) <= 20 ? "text-emerald-400" : (ctrlDrift.overall_drift_score || 0) <= 50 ? "text-amber-400" : "text-red-400"}`}>
                      {ctrlDrift.overall_drift_score ?? "-"}
                    </div>
                    <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Overall Drift</div>
                  </div>
                  <div className="text-center p-3 rounded-lg border border-gray-800">
                    <div className="text-lg font-bold font-mono text-white">{ctrlDrift.allocation_drift?.toFixed(4) ?? "-"}</div>
                    <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Allocation Drift</div>
                  </div>
                  <div className="text-center p-3 rounded-lg border border-gray-800">
                    <div className="text-lg font-bold font-mono text-white">{ctrlDrift.regime_drift?.toFixed(4) ?? "-"}</div>
                    <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Regime Drift</div>
                  </div>
                  <div className="text-center p-3 rounded-lg border border-gray-800">
                    <div className="text-lg font-bold font-mono text-white">{ctrlDrift.risk_drift?.toFixed(4) ?? "-"}</div>
                    <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Risk Drift</div>
                  </div>
                </div>

                {ctrlDrift.drift_sources && ctrlDrift.drift_sources.length > 0 && (
                  <div className="mb-4">
                    <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Drift Sources</div>
                    <div className="space-y-1">
                      {ctrlDrift.drift_sources.map((s: any, i: number) => (
                        <div key={i} className="flex items-center gap-2">
                          <span className="text-[10px] text-gray-300 w-32">{s.source}</span>
                          <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
                            <div className={`h-full rounded-full ${(s.contribution || 0) >= 50 ? "bg-red-500" : (s.contribution || 0) >= 20 ? "bg-amber-500" : "bg-emerald-500"}`}
                              style={{ width: `${Math.min(s.contribution || 0, 100)}%` }}
                            />
                          </div>
                          <span className="text-[10px] font-mono text-gray-400 w-10 text-right">{(s.contribution || 0).toFixed(0)}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {ctrlDrift.risk_warnings && ctrlDrift.risk_warnings.length > 0 && (
                  <div>
                    <div className="text-[10px] text-red-400 uppercase tracking-wider mb-2">Risk Warnings</div>
                    <div className="space-y-1">
                      {ctrlDrift.risk_warnings.map((w: string, i: number) => (
                        <div key={i} className="flex items-center gap-1.5 text-[10px] text-red-300">
                          <span>!</span>
                          <span>{w}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
            {!ctrlDriftLoading && !ctrlDrift && (
              <div className="text-center py-4 text-xs text-muted-foreground">No drift data available.</div>
            )}
          </div>

          {/* C. Feedback Dampening */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
            <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
              <Gauge className="h-3 w-3 inline mr-1" />
              Feedback Dampening
            </h3>
            {ctrlStateLoading && <div className="text-center py-4 text-xs text-muted-foreground">Loading...</div>}
            {!ctrlStateLoading && ctrlState?.dampening && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="text-center p-3 rounded-lg border border-gray-800">
                  <div className={`text-lg font-bold font-mono ${(ctrlState.dampening.global_stability_factor || 0) >= 0.7 ? "text-emerald-400" : (ctrlState.dampening.global_stability_factor || 0) >= 0.4 ? "text-amber-400" : "text-red-400"}`}>
                    {(ctrlState.dampening.global_stability_factor || 0).toFixed(2)}
                  </div>
                  <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Stability Factor</div>
                </div>
                <div className="text-center p-3 rounded-lg border border-gray-800">
                  <div className="text-lg font-bold font-mono text-white">{(ctrlState.dampening.base_learning_rate || 0).toFixed(4)}</div>
                  <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Base LR</div>
                </div>
                <div className="text-center p-3 rounded-lg border border-gray-800">
                  <div className="text-lg font-bold font-mono text-white">{(ctrlState.dampening.regime_instability || 0).toFixed(4)}</div>
                  <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Regime Instability</div>
                </div>
                <div className="text-center p-3 rounded-lg border border-gray-800">
                  <div className="text-lg font-bold font-mono text-white">{(ctrlState.dampening.allocation_variance || 0).toFixed(4)}</div>
                  <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Alloc Variance</div>
                </div>
              </div>
            )}
            {!ctrlStateLoading && (!ctrlState?.dampening) && (
              <div className="text-center py-4 text-xs text-muted-foreground">No dampening data available.</div>
            )}
          </div>

          {/* D. Regime Stability */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
            <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
              <Waves className="h-3 w-3 inline mr-1" />
              Regime Stability
            </h3>
            {ctrlStateLoading && <div className="text-center py-4 text-xs text-muted-foreground">Loading...</div>}
            {!ctrlStateLoading && ctrlState?.regime_transitions?.regimes && ctrlState.regime_transitions.regimes.length > 0 && (
              <>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
                  {ctrlState.regime_transitions.regimes.map((r: any, i: number) => (
                    <div key={r.regime || i} className="text-center p-3 rounded-lg border border-gray-800">
                      <div className="text-sm font-bold font-mono text-white capitalize">{r.regime?.replace(/_/g, " ") || "-"}</div>
                      <div className={`text-lg font-bold font-mono ${(r.probability || 0) >= 0.5 ? "text-emerald-400" : "text-amber-400"}`}>
                        {((r.probability || 0) * 100).toFixed(1)}%
                      </div>
                      <div className="text-[9px] text-gray-500">Persist: {r.persistence_count ?? 0} | Inertia: {(r.inertia || 1).toFixed(2)}</div>
                    </div>
                  ))}
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="text-center p-3 rounded-lg border border-gray-800">
                    <div className="text-lg font-bold font-mono text-white">
                      {ctrlState.regime_transitions.volatility_adjustment?.toFixed(2) ?? "1.00"}x
                    </div>
                    <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Volatility Adjustment</div>
                  </div>
                  <div className="text-center p-3 rounded-lg border border-gray-800">
                    <div className={`text-lg font-bold font-mono ${ctrlState.regime_transitions.regimes.some((r: any) => r.transitions_smoothed) ? "text-emerald-400" : "text-amber-400"}`}>
                      {ctrlState.regime_transitions.regimes.some((r: any) => r.transitions_smoothed) ? "Smoothed" : "Raw"}
                    </div>
                    <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Transition Mode</div>
                  </div>
                </div>
              </>
            )}
            {!ctrlStateLoading && (!ctrlState?.regime_transitions?.regimes || ctrlState.regime_transitions.regimes.length === 0) && (
              <div className="text-center py-4 text-xs text-muted-foreground">No regime data available.</div>
            )}
          </div>
        </div>
      )}

      {/* ── Portfolio Optimization Tab ───────────── */}
      {tab === "portfolio-optimization" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">
              <SlidersHorizontal className="h-3.5 w-3.5 inline mr-1" />
              Portfolio Optimization
            </h2>
            <button
              onClick={handleRunOptimization}
              className="text-[10px] px-3 py-1.5 border border-border rounded hover:border-gray-500 transition-colors"
            >
              Run Optimization
            </button>
          </div>

          {/* A. Optimal Allocation Table */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
            <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
              <PieChart className="h-3 w-3 inline mr-1" />
              Optimal Allocation
            </h3>
            {optPortfolioLoading && <div className="text-center py-4 text-xs text-muted-foreground">Loading...</div>}
            {!optPortfolioLoading && optPortfolio?.allocations && optPortfolio.allocations.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-gray-800 text-[10px] text-gray-500 uppercase tracking-wider">
                      <th className="text-left py-2 pr-2">Strategy</th>
                      <th className="text-right py-2 pr-2">Weight %</th>
                      <th className="text-right py-2 pr-2">Expected Return</th>
                      <th className="text-right py-2 pr-2">Risk Contribution</th>
                      <th className="text-right py-2">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(optPortfolio.allocations || []).map((a: any, i: number) => (
                      <tr key={a.strategy_id || i} className="border-b border-gray-900 hover:bg-gray-900/30">
                        <td className="py-2 pr-2 text-gray-300 font-mono text-[10px]">{(a.strategy_id || "").slice(0, 16)}</td>
                        <td className="py-2 pr-2 text-right font-mono text-white">{a.weight_pct?.toFixed(2)}%</td>
                        <td className={`py-2 pr-2 text-right font-mono ${(a.expected_return || 0) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                          {(a.expected_return * 100).toFixed(4)}%
                        </td>
                        <td className="py-2 pr-2 text-right font-mono text-gray-300">{a.risk_contribution?.toFixed(4)}</td>
                        <td className="py-2 text-right">
                          <span className={`text-[10px] px-1.5 py-0.5 rounded ${a.status === "active" ? "bg-emerald-500/10 text-emerald-400" : "bg-gray-500/10 text-gray-400"}`}>
                            {a.status || "-"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {!optPortfolioLoading && (!optPortfolio?.allocations || optPortfolio.allocations.length === 0) && (
              <div className="text-center py-4 text-xs text-muted-foreground">No allocation data available. Run optimization to generate.</div>
            )}
          </div>

          {/* B. Monte Carlo Panel */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
            <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
              <TrendingDown className="h-3 w-3 inline mr-1" />
              Monte Carlo Simulation
            </h3>
            {optSimulationLoading && <div className="text-center py-4 text-xs text-muted-foreground">Loading...</div>}
            {!optSimulationLoading && optSimulation?.simulation_id && (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                  <div className="text-center p-3 rounded-lg border border-gray-800">
                    <div className={`text-lg font-bold font-mono ${(optSimulation.expected_drawdown || 0) <= 0.2 ? "text-emerald-400" : (optSimulation.expected_drawdown || 0) <= 0.4 ? "text-amber-400" : "text-red-400"}`}>
                      {(optSimulation.expected_drawdown * 100).toFixed(1)}%
                    </div>
                    <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Expected Drawdown</div>
                  </div>
                  <div className="text-center p-3 rounded-lg border border-gray-800">
                    <div className={`text-lg font-bold font-mono text-red-400`}>
                      {(optSimulation.worst_drawdown * 100).toFixed(1)}%
                    </div>
                    <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Worst Drawdown</div>
                  </div>
                  <div className="text-center p-3 rounded-lg border border-gray-800">
                    <div className={`text-lg font-bold font-mono ${(optSimulation.survival_probability || 0) >= 0.8 ? "text-emerald-400" : (optSimulation.survival_probability || 0) >= 0.5 ? "text-amber-400" : "text-red-400"}`}>
                      {(optSimulation.survival_probability * 100).toFixed(1)}%
                    </div>
                    <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Survival Probability</div>
                  </div>
                  <div className="text-center p-3 rounded-lg border border-gray-800">
                    <div className={`text-lg font-bold font-mono ${(optSimulation.sharpe_mean || 0) >= 1 ? "text-emerald-400" : (optSimulation.sharpe_mean || 0) >= 0 ? "text-amber-400" : "text-red-400"}`}>
                      {optSimulation.sharpe_mean?.toFixed(2)}
                    </div>
                    <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Mean Sharpe</div>
                  </div>
                </div>

                {optSimulation.percentile_paths && optSimulation.percentile_paths.length > 0 && (
                  <div>
                    <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Percentile Drawdown Curves</div>
                    <div className="space-y-2">
                      {optSimulation.percentile_paths.map((p: any, i: number) => {
                        const maxDD = Math.max(...(p.drawdown_curve || [0])) * 100;
                        const color = p.percentile === "p5" ? "text-red-400" : p.percentile === "p25" ? "text-amber-400" : p.percentile === "p50" ? "text-white" : p.percentile === "p75" ? "text-emerald-400" : "text-blue-400";
                        const barColor = p.percentile === "p5" ? "bg-red-500" : p.percentile === "p25" ? "bg-amber-500" : p.percentile === "p50" ? "bg-gray-500" : p.percentile === "p75" ? "bg-emerald-500" : "bg-blue-500";
                        return (
                          <div key={p.percentile || i} className="flex items-center gap-3">
                            <span className={`text-[10px] font-mono w-8 ${color}`}>{p.percentile}</span>
                            <div className="flex-1 h-3 bg-gray-800 rounded-full overflow-hidden">
                              <div className={`h-full rounded-full ${barColor}`} style={{ width: `${Math.min(maxDD, 100)}%` }} />
                            </div>
                            <span className="text-[10px] font-mono text-gray-400 w-12 text-right">{maxDD.toFixed(1)}%</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </>
            )}
            {!optSimulationLoading && !optSimulation?.simulation_id && (
              <div className="text-center py-4 text-xs text-muted-foreground">No simulation data available. Run optimization to generate.</div>
            )}
          </div>

          {/* C. Risk Model */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
            <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
              <Shield className="h-3 w-3 inline mr-1" />
              Risk Model
            </h3>
            {optRiskLoading && <div className="text-center py-4 text-xs text-muted-foreground">Loading...</div>}
            {!optRiskLoading && optRisk?.strategies && optRisk.strategies.length > 0 && (
              <>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
                  <div className="text-center p-3 rounded-lg border border-gray-800">
                    <div className="text-lg font-bold font-mono text-white">{optRisk.strategies.length}</div>
                    <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Strategies</div>
                  </div>
                  <div className="text-center p-3 rounded-lg border border-gray-800">
                    <div className={`text-lg font-bold font-mono ${optRisk.adjustment_factor >= 1.5 ? "text-red-400" : "text-amber-400"}`}>
                      {optRisk.adjustment_factor?.toFixed(2)}x
                    </div>
                    <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Risk Adjustment</div>
                  </div>
                  <div className="text-center p-3 rounded-lg border border-gray-800">
                    <div className="text-lg font-bold font-mono text-white">{optRisk.regime || "-"}</div>
                    <div className="text-[9px] text-muted-foreground uppercase mt-0.5">Regime</div>
                  </div>
                </div>

                {optRisk.correlations && Object.keys(optRisk.correlations).length > 0 && (
                  <div>
                    <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Correlation Pairs (top 10)</div>
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="border-b border-gray-800 text-[10px] text-gray-500 uppercase tracking-wider">
                            <th className="text-left py-2 pr-2">Pair</th>
                            <th className="text-right py-2">Correlation</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(optRisk.correlations).slice(0, 10).map(([si, corrRow]: [string, any]) =>
                            Object.entries(corrRow).filter(([sj]) => si < sj).slice(0, 5).map(([sj, c]: [string, any]) => (
                              <tr key={`${si}-${sj}`} className="border-b border-gray-900">
                                <td className="py-2 pr-2 text-gray-300 font-mono text-[10px]">{si.slice(0, 10)} / {sj.slice(0, 10)}</td>
                                <td className={`py-2 text-right font-mono ${Math.abs(c) >= 0.7 ? "text-red-400" : Math.abs(c) >= 0.4 ? "text-amber-400" : "text-emerald-400"}`}>
                                  {c?.toFixed(4)}
                                </td>
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </>
            )}
            {!optRiskLoading && (!optRisk?.strategies || optRisk.strategies.length === 0) && (
              <div className="text-center py-4 text-xs text-muted-foreground">No risk model data available.</div>
            )}
          </div>

          {/* D. Expected Returns */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
            <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
              <TrendingUp className="h-3 w-3 inline mr-1" />
              Expected Returns
            </h3>
            {optExpectedReturnsLoading && <div className="text-center py-4 text-xs text-muted-foreground">Loading...</div>}
            {!optExpectedReturnsLoading && optExpectedReturns?.returns && optExpectedReturns.returns.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-gray-800 text-[10px] text-gray-500 uppercase tracking-wider">
                      <th className="text-left py-2 pr-2">Strategy</th>
                      <th className="text-right py-2 pr-2">Expected Return</th>
                      <th className="text-right py-2 pr-2">Confidence</th>
                      <th className="text-left py-2">Regime Breakdown</th>
                    </tr>
                  </thead>
                  <tbody>
                    {optExpectedReturns.returns.sort((a: any, b: any) => b.expected_return - a.expected_return).map((r: any, i: number) => (
                      <tr key={r.strategy_id || i} className="border-b border-gray-900 hover:bg-gray-900/30">
                        <td className="py-2 pr-2 text-gray-300 font-mono text-[10px]">{(r.strategy_id || "").slice(0, 16)}</td>
                        <td className={`py-2 pr-2 text-right font-mono ${(r.expected_return || 0) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                          {(r.expected_return * 100).toFixed(4)}%
                        </td>
                        <td className="py-2 pr-2 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <div className="w-12 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                              <div className={`h-full rounded-full ${(r.confidence || 0) >= 0.7 ? "bg-emerald-500" : (r.confidence || 0) >= 0.4 ? "bg-amber-500" : "bg-red-500"}`}
                                style={{ width: `${(r.confidence || 0) * 100}%` }}
                              />
                            </div>
                            <span className="font-mono text-[10px] text-white">{(r.confidence * 100).toFixed(0)}%</span>
                          </div>
                        </td>
                        <td className="py-2 text-[10px] text-gray-500">
                          {r.regime_contributions ? Object.entries(r.regime_contributions).map(([reg, val]: [string, any]) => (
                            <span key={reg} className="mr-2">
                              {reg}: {(val * 100).toFixed(2)}%
                            </span>
                          )) : "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {!optExpectedReturnsLoading && (!optExpectedReturns?.returns || optExpectedReturns.returns.length === 0) && (
              <div className="text-center py-4 text-xs text-muted-foreground">No expected returns data available. Run optimization to generate.</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
