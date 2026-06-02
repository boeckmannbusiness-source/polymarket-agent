"use client";

import { useState, useEffect, useCallback } from "react";
import { useMonitoringPortfolio, usePortfolioSnapshot, useMarketExposure } from "@/lib/hooks";
import { useAlertsWs, useMonitoringWs } from "@/hooks/useWebSocket";
import { StatCard } from "@/components/StatCard";
import { HealthBadge } from "@/components/HealthBadge";
import { DriftAlertBanner } from "@/components/DriftAlertBanner";
import { LiveIndicator } from "@/components/LiveIndicator";
import { formatPnl, formatNumber } from "@/lib/utils";
import { api } from "@/lib/api";
import {
  Activity, AlertTriangle, RefreshCw, Radio, ShieldCheck, Gauge, RadioReceiver,
  BarChart3, Server, Zap, Layers,
} from "lucide-react";

export default function MonitoringPage() {
  const { data: monitoring, loading: monLoading } = useMonitoringPortfolio();
  const { data: snapshot } = usePortfolioSnapshot();
  const { data: exposure } = useMarketExposure();
  const { alerts, status: alertsStatus } = useAlertsWs();
  const { driftEvents, status: monWsStatus, isLive } = useMonitoringWs();
  const [wsStats, setWsStats] = useState<any>(null);
  const [latencyData, setLatencyData] = useState<any>(null);
  const [debugMode, setDebugMode] = useState(false);
  const [streamPaused, setStreamPaused] = useState(false);
  const [entityFilter, setEntityFilter] = useState("");

  const fetchStats = useCallback(async () => {
    try {
      const [s, l] = await Promise.all([
        fetch("/api/v1/events/monitoring/ws-stats").then(r => r.json()).catch(() => null),
        fetch("/api/v1/events/monitoring/latency").then(r => r.json()).catch(() => null),
      ]);
      if (s) setWsStats(s);
      if (l) setLatencyData(l);
    } catch {}
  }, []);

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 10000);
    return () => clearInterval(interval);
  }, [fetchStats]);

  const driftDetected = driftEvents.length > 0;
  const driftIssues = driftEvents.slice(0, 5).map((e: any) => `${e.event_type}: ${e.message || ""}`);

  const fillLatency = latencyData?.fill_latency;
  const replayLatency = latencyData?.replay_query;
  const snapshotLatency = latencyData?.snapshot_generation;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Monitoring & Health</h1>
          <p className="text-[10px] text-gray-500 uppercase tracking-wider">Execution health and system status</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setDebugMode(!debugMode)}
            className={`text-[10px] px-2 py-1 border rounded ${debugMode ? "border-amber-500 text-amber-400" : "border-border text-muted-foreground"}`}
          >
            Debug
          </button>
          <LiveIndicator status={monWsStatus} />
          <HealthBadge status="healthy" />
        </div>
      </div>

      <DriftAlertBanner
        driftDetected={driftDetected}
        issues={driftIssues}
      />

      {/* System Status */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard
          title="System Status"
          value={isLive ? "Live" : "Polling"}
          icon={Radio}
          color={isLive ? "positive" : "warning"}
          loading={monLoading}
        />
        <StatCard
          title="Active Positions"
          value={`${snapshot?.open_positions_count ?? 0}`}
          icon={Activity}
          loading={monLoading}
        />
        <StatCard
          title="Total PnL"
          value={formatPnl((snapshot?.unrealized_pnl ?? 0) + (snapshot?.realized_pnl ?? 0))}
          icon={Gauge}
          color={(snapshot?.unrealized_pnl ?? 0) + (snapshot?.realized_pnl ?? 0) >= 0 ? "positive" : "negative"}
          loading={monLoading}
        />
        <StatCard
          title="Drawdown"
          value={`${((snapshot?.drawdown ?? 0) * 100).toFixed(1)}%`}
          icon={AlertTriangle}
          color={(snapshot?.drawdown ?? 0) > 0.1 ? "warning" : "default"}
          loading={monLoading}
        />
      </div>

      {/* Infrastructure panel */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard
          title="WS Connections"
          value={`${wsStats?.connection_count ?? "-"}`}
          icon={Server}
          loading={!wsStats}
        />
        <StatCard
          title="Dedup Cache"
          value={`${wsStats?.dedup_cache_size ?? "-"}`}
          icon={Layers}
          loading={!wsStats}
        />
        <StatCard
          title="Dedup Hit Rate"
          value={wsStats ? `${(wsStats.dedup_hit_rate * 100).toFixed(1)}%` : "-"}
          icon={Zap}
          loading={!wsStats}
        />
        <StatCard
          title="Event Throughput"
          value={latencyData ? `${latencyData.fill_latency?.count_1m ?? 0}/m` : "-"}
          icon={BarChart3}
          loading={!latencyData}
        />
      </div>

      {/* Latency panels */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3">
            Fill Latency
          </h3>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-muted-foreground">p50 (1m)</span>
              <span className="font-mono">{fillLatency?.p50_1m ?? "-"}ms</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">p95 (1m)</span>
              <span className="font-mono">{fillLatency?.p95_1m ?? "-"}ms</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">p99 (15m)</span>
              <span className="font-mono">{fillLatency?.p99_15m ?? "-"}ms</span>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3">
            Snapshot Generation
          </h3>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-muted-foreground">p50 (1m)</span>
              <span className="font-mono">{snapshotLatency?.p50_1m ?? "-"}ms</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">p95 (1m)</span>
              <span className="font-mono">{snapshotLatency?.p95_1m ?? "-"}ms</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">p99 (15m)</span>
              <span className="font-mono">{snapshotLatency?.p99_15m ?? "-"}ms</span>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3">
            Replay Query
          </h3>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-muted-foreground">p50 (1m)</span>
              <span className="font-mono">{replayLatency?.p50_1m ?? "-"}ms</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">p95 (1m)</span>
              <span className="font-mono">{replayLatency?.p95_1m ?? "-"}ms</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">p99 (15m)</span>
              <span className="font-mono">{replayLatency?.p99_15m ?? "-"}ms</span>
            </div>
          </div>
        </div>
      </div>

      {/* Health + Summary */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
            <ShieldCheck className="h-3.5 w-3.5 inline mr-1" />
            Execution Health
          </h2>
          <div className="space-y-3">
            <div className="flex items-center justify-between py-2 border-b border-gray-900">
              <span className="text-xs text-gray-400">Fill Rate</span>
              <span className="text-xs font-bold font-mono text-white">-</span>
            </div>
            <div className="flex items-center justify-between py-2 border-b border-gray-900">
              <span className="text-xs text-gray-400">Pending Orders</span>
              <span className="text-xs font-bold font-mono text-white">0</span>
            </div>
            <div className="flex items-center justify-between py-2 border-b border-gray-900">
              <span className="text-xs text-gray-400">Drift Events (24h)</span>
              <span className={`text-xs font-bold font-mono ${driftEvents.length > 0 ? "text-amber-500" : "text-emerald-500"}`}>
                {driftEvents.length}
              </span>
            </div>
            <div className="flex items-center justify-between py-2">
              <span className="text-xs text-gray-400">Stuck Orders</span>
              <span className="text-xs font-bold font-mono text-emerald-500">None</span>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
            <RefreshCw className="h-3.5 w-3.5 inline mr-1" />
            Portfolio Summary
          </h2>
          <div className="space-y-3">
            <div className="flex items-center justify-between py-2 border-b border-gray-900">
              <span className="text-xs text-gray-400">Total Equity</span>
              <span className="text-xs font-bold font-mono text-white">${formatNumber(snapshot?.total_equity ?? 0)}</span>
            </div>
            <div className="flex items-center justify-between py-2 border-b border-gray-900">
              <span className="text-xs text-gray-400">Net Exposure</span>
              <span className="text-xs font-bold font-mono text-white">${formatNumber(snapshot?.net_exposure ?? 0)}</span>
            </div>
            <div className="flex items-center justify-between py-2 border-b border-gray-900">
              <span className="text-xs text-gray-400">Concentration</span>
              <span className="text-xs font-bold font-mono text-white">
                {exposure ? `${exposure.concentration_risk_pct.toFixed(1)}%` : "-"}
              </span>
            </div>
            <div className="flex items-center justify-between py-2">
              <span className="text-xs text-gray-400">Long / Short</span>
              <span className="text-xs font-bold font-mono">
                <span className="text-emerald-500">${formatNumber(exposure?.total_long_exposure ?? 0)}</span>
                <span className="text-gray-600 mx-1">/</span>
                <span className="text-rose-500">${formatNumber(exposure?.total_short_exposure ?? 0)}</span>
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Live Event Stream + Alert History */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">
              <RadioReceiver className="h-3.5 w-3.5 inline mr-1" />
              Live Event Stream
            </h2>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setStreamPaused(!streamPaused)}
                className={`text-[10px] px-2 py-0.5 border rounded ${streamPaused ? "border-amber-500 text-amber-400" : "border-border"}`}
              >
                {streamPaused ? "Resume" : "Pause"}
              </button>
              <LiveIndicator status={monWsStatus} />
            </div>
          </div>
          {debugMode && (
            <div className="mb-2">
              <input
                type="text"
                placeholder="Filter by entity_type..."
                value={entityFilter}
                onChange={(e) => setEntityFilter(e.target.value)}
                className="w-full px-2 py-1 text-xs bg-black border border-border rounded font-mono"
              />
            </div>
          )}
          <div className="h-64 overflow-y-auto space-y-1">
            {(streamPaused ? [] : driftEvents).length === 0 && (
              <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
                {streamPaused ? "Stream paused" : "Waiting for events..."}
              </div>
            )}
            {(streamPaused ? [] : driftEvents)
              .filter((e: any) => !entityFilter || (e.entity_type || "").includes(entityFilter))
              .map((event: any, i: number) => (
              <div key={event.event_id || i} className="flex items-start gap-2 py-1.5 border-b border-border/30 text-xs">
                <span className="text-[10px] text-muted-foreground font-mono shrink-0 w-14">
                  {new Date(event.timestamp).toLocaleTimeString()}
                </span>
                <span className="text-[10px] text-muted-foreground font-mono shrink-0 w-8">
                  #{event.sequence ?? "-"}
                </span>
                <span className={`font-mono uppercase text-[10px] shrink-0 ${
                  event.severity === "critical" ? "text-red-500" :
                  event.severity === "warning" ? "text-amber-500" : "text-blue-500"
                }`}>
                  {event.event_type}
                </span>
                <span className="text-muted-foreground truncate">
                  {event.message || event.title || JSON.stringify(event.payload || "").slice(0, 60)}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">
              <AlertTriangle className="h-3.5 w-3.5 inline mr-1" />
              Alert History
            </h2>
            <div className="flex items-center gap-2">
              <LiveIndicator status={alertsStatus} />
              <span className="text-xs text-muted-foreground">{alerts.length} alerts</span>
            </div>
          </div>
          <div className="h-64 overflow-y-auto space-y-1">
            {alerts.length === 0 && (
              <div className="flex items-center justify-center h-full text-xs text-muted-foreground">
                No alerts
              </div>
            )}
            {alerts.map((alert: any, i: number) => (
              <div
                key={alert.event_id || alert.id || i}
                className={`flex items-start gap-2 py-1.5 border-b border-border/30 text-xs ${
                  alert.acknowledged ? "opacity-50" : ""
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full mt-1 shrink-0 ${
                  alert.severity === "critical" ? "bg-red-500" :
                  alert.severity === "warning" ? "bg-amber-500" : "bg-blue-500"
                }`} />
                <span className="text-[10px] text-muted-foreground font-mono shrink-0 w-14">
                  {new Date(alert.timestamp).toLocaleTimeString()}
                </span>
                <span className="text-[10px] font-mono uppercase shrink-0 text-muted-foreground">
                  {alert.severity}
                </span>
                <span className="text-muted-foreground truncate">{alert.title || alert.message}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Strategy monitoring */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
          <Gauge className="h-3.5 w-3.5 inline mr-1" />
          Strategy Monitoring
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {(snapshot?.strategy_breakdown || []).map((s: any) => (
            <div key={s.agent_id} className="rounded-lg border border-[var(--border)] p-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-white">{s.agent_id}</span>
                <span className={`text-xs font-mono font-bold ${s.total_pnl >= 0 ? "text-emerald-500" : "text-rose-500"}`}>
                  {formatPnl(s.total_pnl)}
                </span>
              </div>
              <div className="flex items-center gap-3 mt-1 text-[10px] text-gray-500">
                <span>{s.trade_count} trades</span>
                <span>{s.win_rate.toFixed(0)}% WR</span>
              </div>
            </div>
          ))}
          {(!snapshot?.strategy_breakdown || snapshot.strategy_breakdown.length === 0) && (
            <div className="col-span-full text-center py-8 text-gray-500 text-sm">
              No active strategies
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
