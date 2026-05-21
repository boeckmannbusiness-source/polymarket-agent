"use client";

import { useEffect, useState } from "react";
import { api, Wallet } from "@/lib/api";
import { formatPnl, formatPercent, formatAddress } from "@/lib/utils";

export default function WhalesPage() {
  const [wallets, setWallets] = useState<Wallet[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.wallets.leaderboard(50).then(setWallets).catch(console.error).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-gray-500">Loading wallets...</div>;

  return (
    <div>
      <h2 className="mb-4 text-2xl font-bold text-white">Whale Intelligence</h2>
      <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] bg-[var(--card)] text-left text-xs uppercase tracking-wider text-gray-400">
              <th className="px-4 py-3">#</th>
              <th className="px-4 py-3">Wallet</th>
              <th className="px-4 py-3">Trades</th>
              <th className="px-4 py-3">Volume</th>
              <th className="px-4 py-3">PnL</th>
              <th className="px-4 py-3">Win Rate</th>
              <th className="px-4 py-3">Tags</th>
            </tr>
          </thead>
          <tbody>
            {wallets.map((w, i) => (
              <tr key={w.address} className="border-b border-[var(--border)] hover:bg-[var(--card)]">
                <td className="px-4 py-3 text-gray-500">{i + 1}</td>
                <td className="px-4 py-3 font-mono text-white">{formatAddress(w.address)}</td>
                <td className="px-4 py-3 text-gray-400">{w.total_trades}</td>
                <td className="px-4 py-3 text-gray-400">{w.total_volume.toFixed(2)}</td>
                <td className={`px-4 py-3 font-mono ${w.realized_pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                  {formatPnl(w.realized_pnl)}
                </td>
                <td className="px-4 py-3 text-gray-400">{formatPercent(w.win_rate)}</td>
                <td className="px-4 py-3">
                  <div className="flex gap-1">
                    {(w.tags || []).map((tag) => (
                      <span key={tag} className="rounded bg-[var(--primary)]/10 px-2 py-0.5 text-xs text-[var(--primary)]">
                        {tag}
                      </span>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
