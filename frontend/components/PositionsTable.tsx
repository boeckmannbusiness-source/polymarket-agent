"use client";

import { useRouter } from "next/navigation";
import { cn, formatPnl } from "@/lib/utils";
import { ArrowUpDown } from "lucide-react";

interface Position {
  market_id: string;
  market_slug?: string | null;
  market_title?: string | null;
  direction: string;
  size: number;
  entry_price: number;
  current_price?: number | null;
  unrealized_pnl: number;
  realized_pnl: number;
  avg_entry_price: number;
  strategy?: string | null;
  opened_at?: string | null;
  trade_id?: string | null;
}

interface PositionsTableProps {
  positions: Position[];
  loading?: boolean;
}

export function PositionsTable({ positions, loading }: PositionsTableProps) {
  const router = useRouter();

  if (loading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-10 animate-pulse rounded bg-gray-800/50" />
        ))}
      </div>
    );
  }

  if (!positions || positions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-gray-500">
        <ArrowUpDown className="h-8 w-8 mb-2 opacity-30" />
        <p className="text-sm">No positions</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border)] text-left text-[10px] uppercase tracking-widest text-gray-500">
            <th className="px-3 py-2 font-semibold">Market</th>
            <th className="px-3 py-2 font-semibold">Side</th>
            <th className="px-3 py-2 font-semibold text-right">Size</th>
            <th className="px-3 py-2 font-semibold text-right">Avg Entry</th>
            <th className="px-3 py-2 font-semibold text-right">Current</th>
            <th className="px-3 py-2 font-semibold text-right">Unrealized PnL</th>
            <th className="px-3 py-2 font-semibold text-right">Strategy</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((p, i) => (
            <tr
              key={`${p.market_id}-${i}`}
              className="border-b border-[var(--border)] hover:bg-[var(--card)] cursor-pointer transition-colors"
              onClick={() => {
                if (p.trade_id) router.push(`/portfolio/trades/${p.trade_id}`);
              }}
            >
              <td className="px-3 py-2.5">
                <div className="text-white text-xs font-medium truncate max-w-[200px]">
                  {p.market_title || p.market_slug || p.market_id.slice(0, 8)}
                </div>
              </td>
              <td className="px-3 py-2.5">
                <span className={cn(
                  "rounded px-1.5 py-0.5 text-[10px] font-bold uppercase",
                  p.direction === "BUY" ? "bg-emerald-900/40 text-emerald-400" : "bg-rose-900/40 text-rose-400",
                )}>
                  {p.direction}
                </span>
              </td>
              <td className="px-3 py-2.5 text-right font-mono text-white">{p.size.toFixed(2)}</td>
              <td className="px-3 py-2.5 text-right font-mono text-gray-400">{p.avg_entry_price.toFixed(4)}</td>
              <td className="px-3 py-2.5 text-right font-mono text-gray-400">
                {p.current_price?.toFixed(4) ?? "-"}
              </td>
              <td className={cn(
                "px-3 py-2.5 text-right font-mono font-bold",
                p.unrealized_pnl >= 0 ? "text-emerald-500" : "text-rose-500",
              )}>
                {formatPnl(p.unrealized_pnl)}
              </td>
              <td className="px-3 py-2.5 text-right text-gray-500 text-[10px]">
                {p.strategy || "-"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
