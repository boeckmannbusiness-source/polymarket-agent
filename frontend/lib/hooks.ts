import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";

type Fetcher<T> = () => Promise<T>;

interface UseDataResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

function useData<T>(fetcher: Fetcher<T>, intervalMs: number | null): UseDataResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    try {
      setError(null);
      const result = await fetcher();
      setData(result);
    } catch (e: any) {
      setError(e?.message || "Fetch failed");
    } finally {
      setLoading(false);
    }
  }, [fetcher]);

  useEffect(() => {
    fetch();
    if (intervalMs && intervalMs > 0) {
      const id = setInterval(fetch, intervalMs);
      return () => clearInterval(id);
    }
  }, [fetch, intervalMs]);

  return { data, loading, error, refetch: fetch };
}

export function usePortfolioSnapshot() {
  return useData(() => api.portfolio.summary(), 15_000);
}

export function usePortfolioHistory(hours = 168) {
  return useData(() => api.portfolio.history(hours), 30_000);
}

export function usePositions(status?: string) {
  return useData(() => api.portfolio.positions(status), 10_000);
}

export function useStrategies() {
  return useData(() => api.portfolio.strategies(), 60_000);
}

export function useStrategyDetail(agentId: string | null) {
  return useData(
    () => agentId ? api.portfolio.strategyDetail(agentId) : Promise.reject("No agent"),
    agentId ? 60_000 : null,
  );
}

export function useStrategyPnlCurve(agentId: string | null) {
  return useData(
    () => agentId ? api.portfolio.strategyPnlCurve(agentId) : Promise.reject("No agent"),
    agentId ? 60_000 : null,
  );
}

export function useTradeTimeline(tradeId: string | null) {
  return useData(
    () => tradeId ? api.portfolio.tradeTimeline(tradeId) : Promise.reject("No trade"),
    null,
  );
}

export function useMarketExposure() {
  return useData(() => api.portfolio.exposure(), 15_000);
}

export function useMonitoringPortfolio() {
  return useData(() => api.monitoring.portfolioMetrics(), 15_000);
}

export function useMonitoringStrategy(agentId: string | null) {
  return useData(
    () => agentId ? api.monitoring.strategyMetrics(agentId) : Promise.reject("No agent"),
    agentId ? 30_000 : null,
  );
}

// ── Shadow Trading hooks ──────────────────────────

export function useShadowExecutions(status?: string, strategy?: string) {
  return useData(() => api.shadow.executions({ status, strategy }), 30_000);
}

export function useShadowStrategies() {
  return useData(() => api.shadow.strategies(), 60_000);
}

export function useShadowPerformance() {
  return useData(() => api.shadow.performance(), 30_000);
}

export function useShadowAnalytics() {
  return useData(() => api.shadow.analytics(), 60_000);
}

export function useShadowBenchmarks() {
  return useData(() => api.shadow.benchmarks(), 120_000);
}

export function useShadowPromotions() {
  return useData(() => api.shadow.promotions(), 60_000);
}

// ── Tournament hooks ────────────────────────────

export function useTournamentRankings() {
  return useData(() => api.tournament.rankings(), 120_000);
}

export function useAllocations(mode = "equal", capital = 100000) {
  return useData(() => api.tournament.allocations(mode, capital), 120_000);
}

export function useAllAllocations(capital = 100000) {
  return useData(() => api.tournament.allAllocations(capital), 120_000);
}

export function useSimulator(capital = 100000, mode = "equal") {
  return useData(() => api.tournament.simulator(capital, mode), 120_000);
}

export function useAutoPromotions() {
  return useData(() => api.tournament.promotions(), 120_000);
}

// ── Research hooks ─────────────────────────────

export function useResearchRegistry(status?: string) {
  return useData(() => api.research.registry(status), 120_000);
}

export function useResearchChampion() {
  return useData(() => api.research.champion(), 120_000);
}

export function useResearchHealth() {
  return useData(() => api.research.health(), 60_000);
}

export function useResearchReport(strategy: string | null) {
  return useData(
    () => strategy ? api.research.report(strategy) : Promise.reject("No strategy"),
    strategy ? 300_000 : null,
  );
}

export function usePortfolioReport() {
  return useData(() => api.research.portfolioReport(), 300_000);
}

// ── Research Agent hooks ───────────────────────

export function useResearchSignals(lifecycle?: string) {
  return useData(() => api.researchAgents.signals(lifecycle), 60_000);
}

export function useResearchConsensus() {
  return useData(() => api.researchAgents.consensus(), 60_000);
}

export function useResearchAgentHealth() {
  return useData(() => api.researchAgents.health(), 60_000);
}

export function useResearchRegistryStats() {
  return useData(() => api.researchAgents.registry(), 60_000);
}

export function useResearchStatus() {
  return useData(() => api.researchAgents.status(), 30_000);
}
