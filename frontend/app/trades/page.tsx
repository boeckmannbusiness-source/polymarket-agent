"use client";

import { useEffect, useState } from "react";
import { api, Trade } from "@/lib/api";
import { formatPnl, timeAgo } from "@/lib/utils";

export default function TradesPage() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.trades.list({ limit: 100 }).then(setTrades).catch(console.error).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-gray-500">Loading trades...</div>;

  return (
    <div>
      <h2 className="mb-4 text-2xl font-bold text-white">Trades</h2>
      <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] bg-[var(--card)] text-left text-xs uppercase tracking-wider text-gray-400">
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Side</th>
              <th className="px-4 py-3">Outcome</th>
              <th className="px-4 py-3">Size</th>
              <th className="px-4 py-3">Price</th>
              <th className="px-4 py-3">PnL</th>
              <th className="px-4 py-3">Time</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((t) => (
              <tr key={t.id} className="border-b border-[var(--border)] hover:bg-[var(--card)]">
                <td className="px-4 py-3">
                  <span className={`rounded px-2 py-0.5 text-xs ${t.trade_type === "paper" ? "bg-yellow-900 text-yellow-400" : "bg-blue-900 text-blue-400"}`}>
                    {t.trade_type}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className={`flex items-center gap-1.5 ${t.status === "open" ? "text-green-400" : t.status === "closed" ? "text-gray-400" : "text-yellow-400"}`}>
                    <span className={`h-1.5 w-1.5 rounded-full ${t.status === "open" ? "bg-green-400" : t.status === "closed" ? "bg-gray-400" : "bg-yellow-400"}`} />
                    {t.status}
                  </span>
                </td>
                <td className={`px-4 py-3 font-medium ${t.side === "buy" ? "text-green-400" : "text-red-400"}`}>
                  {t.side.toUpperCase()}
                </td>
                <td className="px-4 py-3 text-gray-400">{t.outcome}</td>
                <td className="px-4 py-3 font-mono text-gray-400">{t.size.toFixed(2)}</td>
                <td className="px-4 py-3 font-mono text-gray-400">{t.price?.toFixed(4) ?? "-"}</td>
                <td className={`px-4 py-3 font-mono ${t.pnl && t.pnl >= 0 ? "text-green-400" : t.pnl && t.pnl < 0 ? "text-red-400" : "text-gray-400"}`}>
                  {t.pnl !== null ? formatPnl(t.pnl) : "-"}
                </td>
                <td className="px-4 py-3 text-xs text-gray-500">{timeAgo(t.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
