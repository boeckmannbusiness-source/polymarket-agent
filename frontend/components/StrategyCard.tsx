"use client";

import { useRouter } from "next/navigation";
import { cn, formatPnl } from "@/lib/utils";
import { TrendingUp, TrendingDown, Activity } from "lucide-react";

interface Strategy {
  agent_id: string;
  strategy_name?: string | null;
  total_trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  cumulative_pnl: number;
  realized_pnl: number;
  avg_trade_duration_hours: number;
  max_drawdown: number;
  sharpe_ratio?: number | null;
  total_volume: number;
  total_fees: number;
}

interface StrategyCardProps {
  strategy: Strategy;
  compact?: boolean;
}

export function StrategyCard({ strategy, compact }: StrategyCardProps) {
  const router = useRouter();

  return (
    <div
      className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 hover:border-gray-600 cursor-pointer transition-colors"
      onClick={() => router.push(`/portfolio/strategies/${strategy.agent_id}`)}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-gray-500" />
          <span className="text-sm font-bold text-white">{strategy.agent_id}</span>
        </div>
        <span className={cn(
          "text-sm font-bold font-mono",
          strategy.cumulative_pnl >= 0 ? "text-emerald-500" : "text-rose-500",
        )}>
          {formatPnl(strategy.cumulative_pnl)}
        </span>
      </div>

      <div className={cn("grid gap-3", compact ? "grid-cols-2" : "grid-cols-2 md:grid-cols-4")}>
        <div>
          <div className="text-[10px] text-gray-500 uppercase tracking-wider">Win Rate</div>
          <div className="text-sm font-bold font-mono text-white mt-0.5">{strategy.win_rate.toFixed(1)}%</div>
        </div>
        <div>
          <div className="text-[10px] text-gray-500 uppercase tracking-wider">Trades</div>
          <div className="text-sm font-bold font-mono text-white mt-0.5">{strategy.total_trades}</div>
        </div>
        {!compact && (
          <>
            <div>
              <div className="text-[10px] text-gray-500 uppercase tracking-wider">Sharpe</div>
              <div className={cn(
                "text-sm font-bold font-mono mt-0.5",
                strategy.sharpe_ratio != null && strategy.sharpe_ratio >= 1 ? "text-emerald-500"
                  : strategy.sharpe_ratio != null && strategy.sharpe_ratio >= 0 ? "text-yellow-500"
                  : "text-gray-400",
              )}>
                {strategy.sharpe_ratio?.toFixed(2) ?? "N/A"}
              </div>
            </div>
            <div>
              <div className="text-[10px] text-gray-500 uppercase tracking-wider">Max DD</div>
              <div className="text-sm font-bold font-mono text-rose-500 mt-0.5">
                {(strategy.max_drawdown * 100).toFixed(1)}%
              </div>
            </div>
          </>
        )}
      </div>

      {!compact && (
        <div className="mt-3 flex items-center gap-4 text-[10px] text-gray-500">
          <span>Avg Duration: {strategy.avg_trade_duration_hours.toFixed(1)}h</span>
          <span>Volume: ${strategy.total_volume.toFixed(0)}</span>
          <span>Fees: ${strategy.total_fees.toFixed(2)}</span>
        </div>
      )}
    </div>
  );
}
