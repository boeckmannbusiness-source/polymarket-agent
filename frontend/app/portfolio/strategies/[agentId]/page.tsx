"use client";

import { use } from "react";
import { useRouter } from "next/navigation";
import { useStrategyDetail, useStrategyPnlCurve } from "@/lib/hooks";
import { PnLChart } from "@/components/PnLChart";
import { DrawdownChart } from "@/components/DrawdownChart";
import { StatCard } from "@/components/StatCard";
import { formatPnl } from "@/lib/utils";
import { ArrowLeft, TrendingUp, TrendingDown, Activity, Clock, Gauge } from "lucide-react";

export default function StrategyDetailPage({ params }: { params: Promise<{ agentId: string }> }) {
  const { agentId } = use(params);
  const router = useRouter();
  const { data: strategy, loading } = useStrategyDetail(agentId);
  const { data: pnlCurve } = useStrategyPnlCurve(agentId);

  if (loading && !strategy) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-64 animate-pulse rounded bg-gray-800" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-lg bg-gray-800/50" />
          ))}
        </div>
      </div>
    );
  }

  if (!strategy) {
    return (
      <div className="text-center py-16 text-gray-500">
        <p>Strategy not found</p>
        <button onClick={() => router.push("/portfolio/strategies")} className="text-[var(--primary)] text-sm mt-2 hover:underline">
          Back to strategies
        </button>
      </div>
    );
  }

  const chartData = (pnlCurve || []).map((p: any) => ({
    time: new Date(p.timestamp).toLocaleDateString(),
    value: p.cumulative_pnl,
  }));

  const ddData = (pnlCurve || []).map((p: any) => ({
    time: new Date(p.timestamp).toLocaleDateString(),
    drawdown: p.drawdown,
  }));

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <button
          onClick={() => router.push("/portfolio/strategies")}
          className="text-gray-500 hover:text-white transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div>
          <h1 className="text-xl font-bold text-white">{strategy.agent_id}</h1>
          <p className="text-[10px] text-gray-500 uppercase tracking-wider">{strategy.strategy_name || "Active Strategy"}</p>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard
          title="Cumulative PnL"
          value={formatPnl(strategy.cumulative_pnl)}
          icon={TrendingUp}
          color={strategy.cumulative_pnl >= 0 ? "positive" : "negative"}
        />
        <StatCard
          title="Win Rate"
          value={`${strategy.win_rate.toFixed(1)}%`}
          subtitle={`${strategy.wins}W / ${strategy.losses}L`}
          icon={Activity}
          color={strategy.win_rate >= 50 ? "positive" : strategy.win_rate >= 30 ? "warning" : "negative"}
        />
        <StatCard
          title="Sharpe Ratio"
          value={strategy.sharpe_ratio?.toFixed(2) ?? "N/A"}
          icon={Gauge}
          color={strategy.sharpe_ratio != null && strategy.sharpe_ratio >= 1 ? "positive" : strategy.sharpe_ratio != null && strategy.sharpe_ratio >= 0 ? "warning" : "default"}
        />
        <StatCard
          title="Avg Duration"
          value={`${strategy.avg_trade_duration_hours.toFixed(1)}h`}
          icon={Clock}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-3">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider">Total Trades</div>
          <div className="text-lg font-bold font-mono text-white mt-1">{strategy.total_trades}</div>
        </div>
        <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-3">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider">Max Drawdown</div>
          <div className="text-lg font-bold font-mono text-rose-500 mt-1">{(strategy.max_drawdown * 100).toFixed(1)}%</div>
        </div>
        <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-3">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider">Volume / Fees</div>
          <div className="text-lg font-bold font-mono text-white mt-1">
            ${strategy.total_volume.toFixed(0)} / ${strategy.total_fees.toFixed(2)}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
            <TrendingUp className="h-3.5 w-3.5 inline mr-1" />
            Cumulative PnL Curve
          </h2>
          <PnLChart data={chartData} height={250} color="#10b981" valueLabel="PnL" />
        </div>

        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-2">
            <TrendingDown className="h-3.5 w-3.5 inline mr-1" />
            Drawdown
          </h2>
          <DrawdownChart data={ddData} height={120} />
        </div>
      </div>
    </div>
  );
}
