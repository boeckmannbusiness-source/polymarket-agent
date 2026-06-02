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
