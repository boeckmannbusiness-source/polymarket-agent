"use client";

import { useEffect, useState, useMemo } from "react";
import { api, Market, Wallet, Signal, Trade } from "@/lib/api";
import { formatPnl, formatPercent, formatNumber, confidenceColor } from "@/lib/utils";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell,
} from 'recharts';
import {
  ShieldCheck, AlertTriangle, Activity, TrendingUp,
  DollarSign, PieChart as PieChartIcon, ArrowRightLeft, Play, Square, Cpu
} from "lucide-react";

const MODE_COLORS: Record<string, string> = {
  normal: "#00C853", degraded: "#FFD600", protected: "#FF9800",
  read_only: "#9C27B0", emergency_stop: "#FF1744",
};
const MODE_LABELS: Record<string, string> = {
  normal: "Normal", degraded: "Degraded", protected: "Protected",
  read_only: "Read Only", emergency_stop: "Emergency Stop",
};

export default function PMDashboard() {
  const [summary, setSummary] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [status, setStatus] = useState<any>(null);
  const [rankings, setRankings] = useState<any[]>([]);
  const [slippage, setSlippage] = useState<any>(null);
  const [systemMode, setSystemMode] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [ksLoading, setKsLoading] = useState(false);

  // Simulation state
  const [strategyNames, setStrategyNames] = useState<string[]>([]);
  const [selectedStrategy, setSelectedStrategy] = useState("");
  const [simResult, setSimResult] = useState<any>(null);
  const [simLoading, setSimLoading] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const [summ, hist, stat, ranks, slip, mode] = await Promise.all([
          api.portfolio.summary(),
          api.portfolio.history(168),
          api.health.status(),
          api.analytics.strategySummary(7),
          api.analytics.slippageSummary(7),
          api.system.mode().catch(() => null),
        ]);
        setSummary(summ);
        setHistory(hist);
        setStatus(stat);
        setRankings(ranks.rankings || []);
        setSlippage(slip);
        setSystemMode(mode);
      } catch (e) {
        console.error("Failed to load PM dashboard data", e);
      } finally {
        setLoading(false);
      }
    }
    load();
    api.strategies.names().then(r => {
      setStrategyNames(r.strategies || []);
      if (r.strategies?.length) setSelectedStrategy(r.strategies[0]);
    }).catch(() => {});
  }, []);

  const killSwitchActive = status?.metrics?.kill_switch_active ?? false;

  async function toggleKillSwitch() {
    setKsLoading(true);
    try {
      await api.execution.killSwitch();
      const fresh = await api.health.status();
      setStatus(fresh);
    } catch (e) {
      console.error("Kill switch failed", e);
    }
    setKsLoading(false);
  }

  async function runSimulation() {
    if (!selectedStrategy) return;
    setSimLoading(true);
    setSimResult(null);
    try {
      const result = await api.backtesting.simulate(selectedStrategy);
      setSimResult(result);
    } catch (e) {
      console.error("Simulation failed", e);
    }
    setSimLoading(false);
  }

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
    pnl: h.total_realized_pnl + h.total_unrealized_pnl,
  }));

  const strategyData = rankings.slice(0, 5).map(r => ({
    name: r.strategy,
    pnl: r.total_pnl,
    winRate: r.win_rate,
  }));

  const modeColor = MODE_COLORS[systemMode?.mode] || "#888";
  const modeLabel = MODE_LABELS[systemMode?.mode] || (systemMode?.mode || "").toUpperCase();

  return (
    <div className="min-h-screen bg-black text-gray-300 p-4 md:p-6 font-sans pb-12 md:pb-6">
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
        <div className="flex gap-4 md:gap-6 items-center flex-wrap justify-between md:justify-end">
          <div className="text-left md:text-right">
            <div className="text-[10px] font-bold text-gray-600 uppercase tracking-widest mb-1">Drawdown</div>
            <div className="text-lg md:text-xl font-mono text-rose-500 font-bold">
              -{formatPercent(summary?.drawdown || 0)}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className={`h-2.5 w-2.5 rounded-full ${status?.status === 'healthy' ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-amber-500 shadow-[0_0_8px_rgba(251,191,36,0.5)]'}`} />
            <span className="text-xs md:text-sm font-bold text-white uppercase">{status?.status || 'UNKNOWN'}</span>
          </div>
          {systemMode && (
            <div className="flex items-center gap-1.5 rounded-md border px-2 py-1" style={{ borderColor: modeColor + '40', backgroundColor: modeColor + '10' }}>
              <span className="h-2 w-2 rounded-full" style={{ backgroundColor: modeColor }} />
              <span className="text-[10px] md:text-xs font-bold uppercase tracking-wider" style={{ color: modeColor }}>{modeLabel}</span>
            </div>
          )}
        </div>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-12 gap-6">

        {/* Equity Curve */}
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
                <Tooltip contentStyle={{ backgroundColor: '#000', border: '1px solid #222', borderRadius: '8px', fontSize: '12px' }} itemStyle={{ color: '#fff' }} />
                <Area type="monotone" dataKey="value" stroke="#6366f1" strokeWidth={2} fillOpacity={1} fill="url(#colorValue)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* Portfolio Stats + Kill Switch */}
        <section className="col-span-1 md:col-span-4 space-y-6">
          <div className="rounded-xl border border-gray-900 bg-[#050505] p-6">
            <h3 className="flex items-center gap-2 text-[10px] md:text-sm font-bold text-gray-400 uppercase tracking-widest mb-6">
              <ShieldCheck className="h-4 w-4" />
              Portfolio
            </h3>
            <div className="space-y-4">
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Gross Exposure</span>
                <span className="text-white font-mono">${formatNumber(summary?.total_exposure || 0)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Cash Balance</span>
                <span className="text-white font-mono">${formatNumber(summary?.cash_balance || 0)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Positions</span>
                <span className="text-white font-mono">{summary?.open_positions || 0}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Active Strategies</span>
                <span className="text-white font-mono">{status?.metrics?.active_strategies || 0}</span>
              </div>
            </div>
          </div>

          <div className={`rounded-xl border p-4 flex items-center justify-between ${killSwitchActive ? 'border-rose-900/30 bg-rose-950/5' : 'border-emerald-900/30 bg-emerald-950/5'}`}>
            <div className="flex items-center gap-3">
              <div className={`rounded-full p-2 ${killSwitchActive ? 'bg-rose-500/10 text-rose-500' : 'bg-emerald-500/10 text-emerald-500'}`}>
                <AlertTriangle className="h-5 w-5" />
              </div>
              <div>
                <div className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Emergency</div>
                <div className="text-sm font-bold text-white">Kill-Switch</div>
                <div className="text-[10px] mt-0.5 font-mono">{killSwitchActive ? 'TRADING HALTED' : 'Active — Trading'}</div>
              </div>
            </div>
            <button
              onClick={toggleKillSwitch}
              disabled={ksLoading}
              className={`rounded px-4 py-2 text-xs font-bold text-white transition-colors ${
                killSwitchActive
                  ? 'bg-emerald-600 hover:bg-emerald-500'
                  : 'bg-rose-600 hover:bg-rose-500'
              } disabled:opacity-50`}
            >
              {ksLoading ? '...' : killSwitchActive ? 'RESUME' : 'HALT'}
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
                <span className="text-xl font-mono text-white">{((slippage?.avg_slippage || 0) * 100).toFixed(4)}%</span>
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
              {(summary?.positions || []).slice(0, 4).map((p: any) => (
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

        {/* Strategy Simulation Panel */}
        <section className="col-span-1 md:col-span-12 rounded-xl border border-gray-900 bg-[#050505] p-6">
          <h3 className="flex items-center gap-2 text-[10px] md:text-sm font-bold text-gray-400 uppercase tracking-widest mb-4">
            <Cpu className="h-4 w-4" />
            Strategy Simulation
          </h3>
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <label className="block text-[10px] text-gray-600 uppercase tracking-wider mb-1">Strategy</label>
              <select
                value={selectedStrategy}
                onChange={(e) => setSelectedStrategy(e.target.value)}
                className="rounded border border-gray-800 bg-gray-900 px-3 py-2 text-sm text-white focus:outline-none focus:border-gray-600"
              >
                {strategyNames.map((name) => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
            </div>
            <button
              onClick={runSimulation}
              disabled={simLoading || !selectedStrategy}
              className="flex items-center gap-2 rounded bg-indigo-600 px-4 py-2 text-xs font-bold text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors"
            >
              {simLoading ? <Activity className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
              {simLoading ? 'Running...' : 'Run Simulation'}
            </button>
          </div>

          {simResult && (
            <div className="mt-6 grid grid-cols-2 md:grid-cols-5 gap-4">
              <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-3">
                <div className="text-[10px] text-gray-500 uppercase tracking-wider">Total P&L</div>
                <div className={`text-lg font-bold font-mono mt-1 ${(simResult.metrics?.total_pnl || 0) >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
                  {formatPnl(simResult.metrics?.total_pnl || 0)}
                </div>
              </div>
              <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-3">
                <div className="text-[10px] text-gray-500 uppercase tracking-wider">Win Rate</div>
                <div className="text-lg font-bold font-mono mt-1 text-white">{((simResult.metrics?.win_rate || 0) * 100).toFixed(1)}%</div>
              </div>
              <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-3">
                <div className="text-[10px] text-gray-500 uppercase tracking-wider">Sharpe</div>
                <div className="text-lg font-bold font-mono mt-1 text-white">{(simResult.metrics?.sharpe_ratio || 0).toFixed(2)}</div>
              </div>
              <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-3">
                <div className="text-[10px] text-gray-500 uppercase tracking-wider">Max Drawdown</div>
                <div className="text-lg font-bold font-mono mt-1 text-rose-500">{((simResult.metrics?.max_drawdown || 0) * 100).toFixed(1)}%</div>
              </div>
              <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-3">
                <div className="text-[10px] text-gray-500 uppercase tracking-wider">Trades</div>
                <div className="text-lg font-bold font-mono mt-1 text-white">{simResult.metrics?.total_trades || 0}</div>
              </div>
            </div>
          )}
        </section>

      </div>

      <footer className="fixed bottom-0 left-0 right-0 border-t border-gray-900 bg-black/80 backdrop-blur-md px-6 py-2 flex items-center justify-between text-[8px] md:text-[10px] font-bold text-gray-600 uppercase tracking-[0.2em]">
        <div className="flex items-center gap-4">
          <span className="hidden md:inline">Last Update: {status?.timestamp ? new Date(status.timestamp).toLocaleTimeString() : '---'}</span>
          <span className="hidden md:inline">•</span>
          <span>Env: PROD</span>
        </div>
        <div className="flex items-center gap-4">
          <span className={`${killSwitchActive ? 'text-rose-500/50' : 'text-emerald-500/50'}`}>{killSwitchActive ? 'HALTED' : 'Live'}</span>
          <span className="hidden md:inline">© 2024 PI Agent</span>
        </div>
      </footer>
    </div>
  );
}
