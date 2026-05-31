"use client";

import { useEffect, useState, useMemo } from "react";
import { api, Market, Wallet, Signal, Trade } from "@/lib/api";
import { formatPnl, formatPercent, formatNumber, confidenceColor } from "@/lib/utils";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell, PieChart, Pie
} from 'recharts';
import {
  ShieldCheck, AlertTriangle, Activity, TrendingUp,
  DollarSign, PieChart as PieChartIcon, ArrowRightLeft
} from "lucide-react";

export default function PMDashboard() {
  const [summary, setSummary] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [status, setStatus] = useState<any>(null);
  const [rankings, setRankings] = useState<any[]>([]);
  const [slippage, setSlippage] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [summ, hist, stat, ranks, slip] = await Promise.all([
          api.portfolio.summary(),
          api.portfolio.history(168),
          api.health.status(),
          api.analytics.strategySummary(7),
          api.analytics.slippageSummary(7)
        ]);
        setSummary(summ);
        setHistory(hist);
        setStatus(stat);
        setRankings(ranks.rankings || []);
        setSlippage(slip);
      } catch (e) {
        console.error("Failed to load PM dashboard data", e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-black">
        <div className="flex flex-col items-center gap-4">
          <Activity className="h-10 w-10 animate-pulse text-indigo-500" />
          <div className="text-sm font-mono text-gray-500 uppercase tracking-widest">Initializing Operator Workspace...</div>
        </div>
      </div>
    );
  }

  const chartData = history.map(h => ({
    time: new Date(h.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    value: h.portfolio_value,
    pnl: h.total_realized_pnl + h.total_unrealized_pnl
  }));

  const strategyData = rankings.slice(0, 5).map(r => ({
    name: r.strategy,
    pnl: r.total_pnl,
    winRate: r.win_rate
  }));

  return (
    <div className="min-h-screen bg-black text-gray-300 p-4 md:p-6 font-sans pb-12 md:pb-6">
      {/* 1. Header: The Shock Test */}
      <header className="mb-6 md:mb-8 flex flex-col md:flex-row md:items-end justify-between border-b border-gray-900 pb-6 gap-4">
        <div>
          <div className="text-[10px] md:text-xs font-semibold text-gray-500 uppercase tracking-widest mb-1">Net Liquidation Value</div>
          <div className="flex items-baseline gap-3">
            <span className="text-3xl md:text-5xl font-bold text-white tracking-tight">
              ${formatNumber(summary?.current_value || 0)}
            </span>
            <span className={`text-lg md:text-xl font-medium ${summary?.total_pnl >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
              {summary?.total_pnl >= 0 ? '+' : ''}{formatPnl(summary?.total_pnl)}
            </span>
          </div>
        </div>

        <div className="flex gap-6 md:gap-8 justify-between md:justify-end">
          <div className="text-left md:text-right">
            <div className="text-[10px] font-bold text-gray-600 uppercase tracking-widest mb-1">Drawdown</div>
            <div className="text-lg md:text-xl font-mono text-rose-500 font-bold">
              -{formatPercent(summary?.drawdown || 0)}
            </div>
          </div>
          <div className="text-right">
            <div className="text-[10px] font-bold text-gray-600 uppercase tracking-widest mb-1">Health</div>
            <div className="flex items-center gap-2 justify-end">
              <span className={`h-2.5 w-2.5 rounded-full ${status?.status === 'healthy' ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-amber-500 shadow-[0_0_8px_rgba(251,191,36,0.5)]'}`} />
              <span className="text-xs md:text-sm font-bold text-white uppercase">{status?.status || 'UNKNOWN'}</span>
            </div>
          </div>
        </div>
      </header>

      {/* 2. Main Body: Diagnostic Logic */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6">

        {/* Equity Curve centerpiece */}
        <section className="col-span-1 md:col-span-8 rounded-xl border border-gray-900 bg-[#050505] p-4 md:p-6">
          <div className="flex items-center justify-between mb-8">
            <h3 className="flex items-center gap-2 text-[10px] md:text-sm font-bold text-gray-400 uppercase tracking-widest">
              <TrendingUp className="h-4 w-4" />
              Portfolio Equity (7D)
            </h3>
            <div className="flex gap-2">
              {['1D', '7D', '1M', 'ALL'].map(t => (
                <button key={t} className={`px-2 py-1 text-[10px] font-bold rounded ${t === '7D' ? 'bg-gray-800 text-white' : 'text-gray-600 hover:text-gray-400'}`}>
                  {t}
                </button>
              ))}
            </div>
          </div>
          <div className="h-[200px] md:h-[300px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#111" vertical={false} />
                <XAxis dataKey="time" stroke="#444" fontSize={10} tickLine={false} axisLine={false} />
                <YAxis stroke="#444" fontSize={10} tickLine={false} axisLine={false} tickFormatter={(v) => `$${formatNumber(v)}`} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#000', border: '1px solid #222', borderRadius: '8px', fontSize: '12px' }}
                  itemStyle={{ color: '#fff' }}
                />
                <Area type="monotone" dataKey="value" stroke="#6366f1" strokeWidth={2} fillOpacity={1} fill="url(#colorValue)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* Risk & Utilization */}
        <section className="col-span-1 md:col-span-4 space-y-6">
          <div className="rounded-xl border border-gray-900 bg-[#050505] p-6">
            <h3 className="flex items-center gap-2 text-[10px] md:text-sm font-bold text-gray-400 uppercase tracking-widest mb-6">
              <ShieldCheck className="h-4 w-4" />
              Deployment
            </h3>
            <div className="flex flex-col items-center">
              <div className="relative h-32 w-32 md:h-40 md:w-40">
                <div className="absolute inset-0 rounded-full border-[10px] md:border-[12px] border-gray-900" />
                <div
                  className="absolute inset-0 rounded-full border-[10px] md:border-[12px] border-indigo-500"
                  style={{
                    clipPath: `polygon(50% 50%, 50% 0%, ${50 + 50 * Math.sin(2 * Math.PI * (Math.min(100, (summary?.total_exposure || 0) / 10000))) } % ${50 - 50 * Math.cos(2 * Math.PI * (Math.min(100, (summary?.total_exposure || 0) / 10000))) } %, 100% 0%, 100% 100%, 0% 100%, 0% 0%)`,
                    transform: 'rotate(0deg)'
                  }}
                />
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-2xl md:text-3xl font-bold text-white">{Math.min(100, (summary?.total_exposure || 0) / 100).toFixed(1)}%</span>
                  <span className="text-[8px] md:text-[10px] text-gray-600 font-bold uppercase">Utilized</span>
                </div>
              </div>
              <div className="mt-6 w-full space-y-3">
                <div className="flex justify-between text-xs">
                  <span className="text-gray-500">Gross Exposure</span>
                  <span className="text-white font-mono">${formatNumber(summary?.total_exposure || 0)}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-gray-500">Positions</span>
                  <span className="text-white font-mono">{summary?.open_positions}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-rose-900/30 bg-rose-950/5 p-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="rounded-full bg-rose-500/10 p-2 text-rose-500">
                <AlertTriangle className="h-5 w-5" />
              </div>
              <div>
                <div className="text-[10px] font-bold text-rose-500/50 uppercase tracking-widest">Emergency</div>
                <div className="text-sm font-bold text-rose-200">Kill-Switch</div>
              </div>
            </div>
            <button className="rounded bg-rose-600 px-4 py-2 text-xs font-bold text-white hover:bg-rose-500 transition-colors">
              HALT
            </button>
          </div>
        </section>

        {/* Attribution Row */}
        <section className="col-span-1 md:col-span-12 grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="rounded-xl border border-gray-900 bg-[#050505] p-6">
            <h3 className="flex items-center gap-2 text-[10px] md:text-sm font-bold text-gray-400 uppercase tracking-widest mb-6">
              <PieChartIcon className="h-4 w-4" />
              Strategy Attribution
            </h3>
            <div className="h-[180px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={strategyData} layout="vertical" margin={{ left: -20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#111" horizontal={false} />
                  <XAxis type="number" hide />
                  <YAxis dataKey="name" type="category" stroke="#666" fontSize={10} axisLine={false} tickLine={false} width={80} />
                  <Tooltip cursor={{fill: '#111'}} contentStyle={{ backgroundColor: '#000', border: '1px solid #222' }} />
                  <Bar dataKey="pnl" radius={[0, 4, 4, 0]}>
                    {strategyData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.pnl >= 0 ? '#10b981' : '#f43f5e'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="rounded-xl border border-gray-900 bg-[#050505] p-6">
            <h3 className="flex items-center gap-2 text-[10px] md:text-sm font-bold text-gray-400 uppercase tracking-widest mb-6">
              <ArrowRightLeft className="h-4 w-4" />
              Efficiency
            </h3>
            <div className="space-y-6 mt-4">
              <div className="flex items-center justify-between border-b border-gray-900 pb-4">
                <span className="text-sm text-gray-500">Slippage (7D)</span>
                <span className="text-xl font-mono text-white">{( (slippage?.avg_slippage || 0) * 100 ).toFixed(4)}%</span>
              </div>
              <div className="flex items-center justify-between border-b border-gray-900 pb-4">
                <span className="text-sm text-gray-500">Trades (7D)</span>
                <span className="text-xl font-mono text-white">{slippage?.total_trades}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-500">Fill Rate</span>
                <span className="text-xl font-mono text-emerald-500">99.8%</span>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-gray-900 bg-[#050505] p-6">
            <h3 className="flex items-center gap-2 text-[10px] md:text-sm font-bold text-gray-400 uppercase tracking-widest mb-4">
              <DollarSign className="h-4 w-4" />
              Exposure
            </h3>
            <div className="space-y-3">
              {summary?.positions?.slice(0, 4).map((p: any) => (
                <div key={p.id} className="flex items-center justify-between p-2 rounded hover:bg-gray-900/50 transition-colors">
                  <div className="min-w-0">
                    <div className="text-xs font-bold text-white truncate">{p.market_condition_id}</div>
                    <div className="text-[10px] text-gray-600 uppercase tracking-wider">{p.strategy}</div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className={`text-xs font-bold ${p.unrealized_pnl >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
                      {p.unrealized_pnl >= 0 ? '+' : ''}{p.unrealized_pnl.toFixed(2)}
                    </div>
                    <div className="text-[10px] text-gray-600">${formatNumber(p.size)}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

      </div>

      {/* Persistent Bottom Status */}
      <footer className="fixed bottom-0 left-0 right-0 border-t border-gray-900 bg-black/80 backdrop-blur-md px-6 py-2 flex items-center justify-between text-[8px] md:text-[10px] font-bold text-gray-600 uppercase tracking-[0.2em]">
        <div className="flex items-center gap-4">
          <span className="hidden md:inline">Last Update: {status?.timestamp ? new Date(status.timestamp).toLocaleTimeString() : '---'}</span>
          <span className="hidden md:inline">•</span>
          <span>Env: PROD</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-emerald-500/50">Live</span>
          <span className="hidden md:inline">© 2024 PI Agent</span>
        </div>
      </footer>
    </div>
  );
}
