"use client";

import { useRouter } from "next/navigation";
import {
  usePortfolioSnapshot, usePositions, useStrategies, useMarketExposure,
} from "@/lib/hooks";
import { StatCard } from "@/components/StatCard";
import { PositionsTable } from "@/components/PositionsTable";
import { PnLChart } from "@/components/PnLChart";
import { StrategyCard } from "@/components/StrategyCard";
import { ExposurePanel } from "@/components/ExposurePanel";
import { HealthBadge } from "@/components/HealthBadge";
import { formatPnl, formatPercent, formatNumber } from "@/lib/utils";
import {
  DollarSign, TrendingUp, TrendingDown, Activity, AlertTriangle,
  BarChart3, LayoutDashboard, ArrowRight,
} from "lucide-react";

export default function PortfolioPage() {
  const router = useRouter();
  const { data: snapshot, loading: snapLoading } = usePortfolioSnapshot();
  const { data: positions } = usePositions("OPEN");
  const { data: strategies } = useStrategies();
  const { data: exposure } = useMarketExposure();

  if (snapLoading && !snapshot) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 animate-pulse rounded bg-gray-800" />
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-lg bg-gray-800/50" />
          ))}
        </div>
      </div>
    );
  }

  const chartData = snapshot?.positions?.map((p: any, i: number) => ({
    time: `${p.market_slug || p.market_id?.slice(0, 8) || i}`,
    value: p.unrealized_pnl + (p.size * (p.current_price || p.entry_price)),
  })).slice(0, 20) || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-white">Portfolio Overview</h1>
        <HealthBadge status="healthy" />
      </div>

      {/* Summary strip */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <StatCard
          title="Total Equity"
          value={`$${formatNumber(snapshot?.total_equity ?? 0)}`}
          icon={DollarSign}
          color={snapshot?.total_equity >= 0 ? "positive" : "negative"}
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
          title="Realized PnL"
          value={formatPnl(snapshot?.realized_pnl ?? 0)}
          icon={TrendingDown}
          color={(snapshot?.realized_pnl ?? 0) >= 0 ? "positive" : "negative"}
          loading={snapLoading}
        />
        <StatCard
          title="Net Exposure"
          value={`$${formatNumber(snapshot?.net_exposure ?? 0)}`}
          icon={BarChart3}
          color="default"
          loading={snapLoading}
        />
        <StatCard
          title="Open Positions"
          value={`${snapshot?.open_positions_count ?? 0}`}
          icon={Activity}
          loading={snapLoading}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Strategy breakdown */}
        <div className="md:col-span-2 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">
              <Activity className="h-3.5 w-3.5 inline mr-1" />
              Strategy Breakdown
            </h2>
            <button
              onClick={() => router.push("/portfolio/strategies")}
              className="text-[10px] text-[var(--primary)] hover:underline flex items-center gap-1"
            >
              View All <ArrowRight className="h-3 w-3" />
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {(snapshot?.strategy_breakdown || []).slice(0, 4).map((s: any) => (
              <div
                key={s.agent_id}
                className="rounded-lg border border-[var(--border)] p-3 hover:border-gray-600 cursor-pointer transition-colors"
                onClick={() => router.push(`/portfolio/strategies/${s.agent_id}`)}
              >
                <div className="text-xs font-bold text-white truncate">{s.agent_id}</div>
                <div className="flex items-center justify-between mt-2 text-[10px]">
                  <span className="text-gray-500">PnL</span>
                  <span className={`font-mono font-bold ${s.total_pnl >= 0 ? "text-emerald-500" : "text-rose-500"}`}>
                    {formatPnl(s.total_pnl)}
                  </span>
                </div>
                <div className="flex items-center justify-between text-[10px]">
                  <span className="text-gray-500">Win Rate</span>
                  <span className="font-mono text-gray-300">{s.win_rate.toFixed(1)}%</span>
                </div>
                <div className="flex items-center justify-between text-[10px]">
                  <span className="text-gray-500">Trades</span>
                  <span className="font-mono text-gray-300">{s.trade_count}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Top markets */}
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
            <BarChart3 className="h-3.5 w-3.5 inline mr-1" />
            Top Markets
          </h2>
          <div className="space-y-2">
            {(snapshot?.top_markets || []).slice(0, 6).map((m: any, i: number) => (
              <div key={i} className="flex items-center justify-between py-1.5 border-b border-gray-900 last:border-0">
                <span className="text-xs text-white truncate max-w-[160px]">
                  {m.market_slug || m.market_id?.slice(0, 8)}
                </span>
                <span className="text-xs font-mono text-gray-400">
                  ${m.exposure_value.toFixed(2)}
                  <span className="text-[10px] text-gray-600 ml-1">({m.pct_of_portfolio.toFixed(1)}%)</span>
                </span>
              </div>
            ))}
            {(!snapshot?.top_markets || snapshot.top_markets.length === 0) && (
              <div className="text-sm text-gray-600 text-center py-8">No active positions</div>
            )}
          </div>
        </div>
      </div>

      {/* Open Positions */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)]">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)]">
          <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">
            <Activity className="h-3.5 w-3.5 inline mr-1" />
            Open Positions
          </h2>
          <button
            onClick={() => router.push("/portfolio/positions")}
            className="text-[10px] text-[var(--primary)] hover:underline flex items-center gap-1"
          >
            View All <ArrowRight className="h-3 w-3" />
          </button>
        </div>
        <PositionsTable positions={positions || []} loading={snapLoading} />
      </div>

      {/* Strategies */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">
            <Activity className="h-3.5 w-3.5 inline mr-1" />
            Strategies
          </h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {(strategies || []).slice(0, 6).map((s: any) => (
            <StrategyCard key={s.agent_id} strategy={s} compact />
          ))}
          {(!strategies || strategies.length === 0) && (
            <div className="text-sm text-gray-600 text-center py-8 col-span-full">
              No strategy data available
            </div>
          )}
        </div>
      </div>

      {/* Exposure */}
      {exposure && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
            <BarChart3 className="h-3.5 w-3.5 inline mr-1" />
            Market Exposure
          </h2>
          <ExposurePanel
            totalLong={exposure.total_long_exposure}
            totalShort={exposure.total_short_exposure}
            netExposure={exposure.net_exposure}
            concentrationRisk={exposure.concentration_risk_pct}
            largestPositions={exposure.largest_positions || []}
            exposureByMarket={exposure.exposure_by_market || []}
          />
        </div>
      )}
    </div>
  );
}
