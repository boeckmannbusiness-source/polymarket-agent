"use client";

import { useEffect, useState } from "react";
import { api, Market, Wallet, Signal, Trade } from "@/lib/api";
import { formatPnl, formatPercent, formatNumber, confidenceColor } from "@/lib/utils";

export default function Dashboard() {
  const [markets, setMarkets] = useState<Market[]>([]);
  const [wallets, setWallets] = useState<Wallet[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [m, w, s, t] = await Promise.all([
          api.markets.list({ limit: 5 }),
          api.wallets.leaderboard(5),
          api.signals.list({ limit: 5, is_active: true }),
          api.trades.list({ limit: 5 }),
        ]);
        setMarkets(m);
        setWallets(w);
        setSignals(s);
        setTrades(t);
      } catch (e) {
        console.error("Failed to load dashboard data", e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="text-gray-500">Loading dashboard...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-white">Dashboard</h2>

      <div className="grid grid-cols-4 gap-4">
        <StatCard label="Active Markets" value={markets.length.toString()} />
        <StatCard label="Tracked Wallets" value={wallets.length.toString()} />
        <StatCard label="Active Signals" value={signals.length.toString()} />
        <StatCard label="Recent Trades" value={trades.length.toString()} />
      </div>

      <div className="grid grid-cols-2 gap-6">
        <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
          <h3 className="mb-3 text-sm font-semibold text-gray-400 uppercase tracking-wider">Top Markets</h3>
          <div className="space-y-2">
            {markets.map((m) => (
              <div key={m.id} className="flex items-center justify-between rounded bg-[var(--background)] px-3 py-2 text-sm">
                <span className="truncate text-white">{m.title || m.slug || m.condition_id.slice(0, 10)}</span>
                <span className="text-gray-400">{formatNumber(m.volume)}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
          <h3 className="mb-3 text-sm font-semibold text-gray-400 uppercase tracking-wider">Top Wallets</h3>
          <div className="space-y-2">
            {wallets.map((w) => (
              <div key={w.address} className="flex items-center justify-between rounded bg-[var(--background)] px-3 py-2 text-sm">
                <span className="font-mono text-white">{w.address.slice(0, 8)}...</span>
                <span className={w.realized_pnl >= 0 ? "text-green-400" : "text-red-400"}>
                  {formatPnl(w.realized_pnl)}
                </span>
              </div>
            ))}
          </div>
        </section>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
          <h3 className="mb-3 text-sm font-semibold text-gray-400 uppercase tracking-wider">Recent Signals</h3>
          <div className="space-y-2">
            {signals.map((s) => (
              <div key={s.id} className="flex items-center justify-between rounded bg-[var(--background)] px-3 py-2 text-sm">
                <div className="flex items-center gap-2">
                  <span className={`h-2 w-2 rounded-full ${confidenceColor(s.confidence)}`} />
                  <span className="capitalize text-white">{s.signal_type}</span>
                  <span className={`text-xs font-medium uppercase ${s.direction === "bullish" ? "text-green-400" : s.direction === "bearish" ? "text-red-400" : "text-yellow-400"}`}>
                    {s.direction}
                  </span>
                </div>
                <span className="font-mono text-gray-400">{(s.confidence * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
          <h3 className="mb-3 text-sm font-semibold text-gray-400 uppercase tracking-wider">Active Trades</h3>
          <div className="space-y-2">
            {trades.map((t) => (
              <div key={t.id} className="flex items-center justify-between rounded bg-[var(--background)] px-3 py-2 text-sm">
                <div className="flex items-center gap-2">
                  <span className={`h-2 w-2 rounded-full ${t.status === "open" ? "bg-green-500" : t.status === "pending" ? "bg-yellow-500" : "bg-gray-500"}`} />
                  <span className="capitalize text-white">{t.status}</span>
                  <span className="text-gray-400">{t.outcome}</span>
                </div>
                <span className={t.pnl && t.pnl >= 0 ? "text-green-400" : "text-red-400"}>
                  {formatPnl(t.pnl)}
                </span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
      <div className="text-2xl font-bold text-white">{value}</div>
      <div className="mt-1 text-xs text-gray-500 uppercase tracking-wider">{label}</div>
    </div>
  );
}
