"use client";

import { useEffect, useState } from "react";
import { api, Market } from "@/lib/api";
import { formatNumber } from "@/lib/utils";

export default function MarketsPage() {
  const [markets, setMarkets] = useState<Market[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.markets.list({ limit: 50 }).then(setMarkets).catch(console.error).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-gray-500">Loading markets...</div>;

  return (
    <div>
      <h2 className="mb-4 text-2xl font-bold text-white">Markets</h2>
      <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] bg-[var(--card)] text-left text-xs uppercase tracking-wider text-gray-400">
              <th className="px-4 py-3">Market</th>
              <th className="px-4 py-3">Volume</th>
              <th className="px-4 py-3">Liquidity</th>
              <th className="px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {markets.map((m) => (
              <tr key={m.id} className="border-b border-[var(--border)] hover:bg-[var(--card)]">
                <td className="px-4 py-3 text-white">{m.title || m.slug || m.condition_id.slice(0, 16)}</td>
                <td className="px-4 py-3 text-gray-400">{formatNumber(m.volume)}</td>
                <td className="px-4 py-3 text-gray-400">{formatNumber(m.liquidity)}</td>
                <td className="px-4 py-3">
                  <span className={`rounded-full px-2 py-0.5 text-xs ${m.resolved ? "bg-gray-700 text-gray-400" : "bg-green-900 text-green-400"}`}>
                    {m.resolved ? "Resolved" : "Active"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
