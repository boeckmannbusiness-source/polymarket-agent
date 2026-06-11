"use client";

import { useState, useEffect, useCallback } from "react";
import { StatCard } from "@/components/StatCard";
import { useMonitoringWs } from "@/hooks/useWebSocket";
import {
  Activity, Shield, AlertTriangle, Clock, BarChart3, Zap,
  TrendingUp, TrendingDown, CheckCircle, XCircle, Eye,
  Server, Database, RefreshCw,
} from "lucide-react";

type ValidationStatus = "HEALTHY" | "WARNING" | "CRITICAL";

export default function ValidationPage() {
  const [status, setStatus] = useState<ValidationStatus>("HEALTHY");
  const [startTime, setStartTime] = useState<string>("");
  const [elapsedHours, setElapsedHours] = useState(0);
  const [progressPct, setProgressPct] = useState(0);
  const [snapshotCount, setSnapshotCount] = useState(0);
  const [activeAlertCount, setActiveAlertCount] = useState(0);
  const [latestSnapshot, setLatestSnapshot] = useState<any>(null);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { driftEvents } = useMonitoringWs();

  const fetchData = useCallback(async () => {
    try {
      const [statusRes, snapRes, alertsRes] = await Promise.all([
        fetch("/api/v1/shadow-validation/monitor/status").then(r => r.json()).catch(() => null),
        fetch("/api/v1/shadow-validation/monitor/latest-snapshot").then(r => r.json()).catch(() => null),
        fetch("/api/v1/shadow-validation/monitor/alerts").then(r => r.json()).catch(() => null),
      ]);

      if (statusRes) {
        setStatus(statusRes.status);
        setStartTime(statusRes.start_time);
        setElapsedHours(statusRes.elapsed_hours);
        setProgressPct(statusRes.progress_pct);
        setSnapshotCount(statusRes.snapshot_count);
        setActiveAlertCount(statusRes.active_alert_count);
      }
      if (snapRes && !snapRes.detail) {
        setLatestSnapshot(snapRes);
      }
      if (alertsRes) {
        setAlerts(alertsRes.alerts || []);
      }
      setError(null);
    } catch (e: any) {
      setError(e?.message || "Fetch failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const statusColor = status === "HEALTHY" ? "text-emerald-500" : status === "WARNING" ? "text-yellow-500" : "text-rose-500";
  const statusBg = status === "HEALTHY" ? "bg-emerald-500/10 border-emerald-500/30" : status === "WARNING" ? "bg-yellow-500/10 border-yellow-500/30" : "bg-rose-500/10 border-rose-500/30";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-white">Shadow Validation Monitor</h1>
        <button
          onClick={fetchData}
          className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white transition-colors"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-400">
          {error}
        </div>
      )}

      <div className={`rounded-lg border p-4 ${statusBg}`}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className={`h-3 w-3 rounded-full ${status === "HEALTHY" ? "bg-emerald-500" : status === "WARNING" ? "bg-yellow-500" : "bg-rose-500"}`} />
            <span className={`text-lg font-bold font-mono ${statusColor}`}>{status}</span>
          </div>
          <span className="text-xs text-gray-500 font-mono">
            {snapshotCount} snapshots
          </span>
        </div>

        <div className="w-full bg-gray-800 rounded-full h-2.5 mb-1">
          <div
            className={`h-2.5 rounded-full transition-all duration-500 ${
              progressPct < 50 ? "bg-emerald-500" : progressPct < 90 ? "bg-yellow-500" : "bg-emerald-500"
            }`}
            style={{ width: `${Math.min(progressPct, 100)}%` }}
          />
        </div>
        <div className="flex justify-between text-[10px] text-gray-500">
          <span>0h</span>
          <span className="font-mono text-gray-400">{elapsedHours.toFixed(1)}h / 72h</span>
          <span>72h</span>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard
          title="Market Data Events"
          value={(latestSnapshot?.market_data_count ?? 0).toLocaleString()}
          icon={Activity}
          color={latestSnapshot?.market_data_count > 0 ? "default" : "warning"}
        />
        <StatCard
          title="Wallet Trades"
          value={(latestSnapshot?.wallet_trade_count ?? 0).toLocaleString()}
          icon={TrendingUp}
          color={latestSnapshot?.wallet_trade_count > 0 ? "default" : "warning"}
        />
        <StatCard
          title="Signals"
          value={(latestSnapshot?.signal_count ?? 0).toLocaleString()}
          icon={Zap}
          color={latestSnapshot?.signal_count > 0 ? "default" : "warning"}
        />
        <StatCard
          title="Trade Requests"
          value={(latestSnapshot?.trade_request_count ?? 0).toLocaleString()}
          icon={BarChart3}
          color={latestSnapshot?.trade_request_count > 0 ? "default" : "warning"}
        />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard
          title="Shadow Decisions"
          value={(latestSnapshot?.shadow_decision_count ?? 0).toLocaleString()}
          icon={Shield}
          color={latestSnapshot?.shadow_decision_count > 0 ? "default" : "warning"}
        />
        <StatCard
          title="Risk Approved"
          value={(latestSnapshot?.risk_approved_count ?? 0).toLocaleString()}
          icon={CheckCircle}
          color="positive"
        />
        <StatCard
          title="Risk Rejected"
          value={(latestSnapshot?.risk_rejected_count ?? 0).toLocaleString()}
          icon={XCircle}
          color="negative"
        />
        <StatCard
          title="Exception Count"
          value={(latestSnapshot?.exception_count ?? 0).toLocaleString()}
          icon={AlertTriangle}
          color={(latestSnapshot?.exception_count ?? 0) > 0 ? "negative" : "default"}
        />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard
          title="Shadow Approved"
          value={(latestSnapshot?.shadow_approved_count ?? 0).toLocaleString()}
          icon={CheckCircle}
          color="positive"
        />
        <StatCard
          title="Shadow Blocked"
          value={(latestSnapshot?.shadow_blocked_count ?? 0).toLocaleString()}
          icon={Shield}
          color="negative"
        />
        <StatCard
          title="Unique Wallets"
          value={(latestSnapshot?.unique_wallets ?? 0).toLocaleString()}
          icon={Eye}
        />
        <StatCard
          title="Unique Markets"
          value={(latestSnapshot?.unique_markets ?? 0).toLocaleString()}
          icon={Database}
        />
      </div>

      <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
        <div className="flex items-center gap-2 mb-3">
          <AlertTriangle className="h-4 w-4 text-yellow-500" />
          <h2 className="text-sm font-semibold text-white">Active Alerts</h2>
          {activeAlertCount > 0 && (
            <span className="text-[10px] font-mono bg-rose-500/20 text-rose-400 px-1.5 py-0.5 rounded">
              {activeAlertCount}
            </span>
          )}
        </div>
        {alerts.length === 0 ? (
          <p className="text-xs text-gray-500">No active alerts. System is healthy.</p>
        ) : (
          <div className="space-y-2">
            {alerts.map((alert, i) => (
              <div
                key={i}
                className={`rounded border p-2.5 text-xs ${
                  alert.severity === "CRITICAL"
                    ? "border-rose-500/30 bg-rose-500/5"
                    : alert.severity === "HIGH"
                    ? "border-yellow-500/30 bg-yellow-500/5"
                    : "border-gray-700 bg-gray-800/50"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-white">{alert.alert_type}</span>
                  <span className={`font-mono text-[10px] ${
                    alert.severity === "CRITICAL" ? "text-rose-400" : alert.severity === "HIGH" ? "text-yellow-400" : "text-gray-400"
                  }`}>
                    {alert.severity}
                  </span>
                </div>
                <p className="text-gray-400">{alert.message}</p>
                <p className="text-gray-600 mt-1 font-mono">{alert.timestamp}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {latestSnapshot && (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
          <div className="flex items-center gap-2 mb-3">
            <Clock className="h-4 w-4 text-gray-500" />
            <h2 className="text-sm font-semibold text-white">Last Snapshot</h2>
            <span className="text-[10px] text-gray-500 font-mono ml-auto">
              {latestSnapshot.timestamp}
            </span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
            <div className="text-gray-500">Market Data Events</div>
            <div className="text-white font-mono text-right">{latestSnapshot.market_data_count.toLocaleString()}</div>
            <div className="text-gray-500">Wallet Trades</div>
            <div className="text-white font-mono text-right">{latestSnapshot.wallet_trade_count.toLocaleString()}</div>
            <div className="text-gray-500">Signals</div>
            <div className="text-white font-mono text-right">{latestSnapshot.signal_count.toLocaleString()}</div>
            <div className="text-gray-500">Trade Requests</div>
            <div className="text-white font-mono text-right">{latestSnapshot.trade_request_count.toLocaleString()}</div>
            <div className="text-gray-500">Shadow Decisions</div>
            <div className="text-white font-mono text-right">{latestSnapshot.shadow_decision_count.toLocaleString()}</div>
            <div className="text-gray-500">Risk Approved</div>
            <div className="text-emerald-400 font-mono text-right">{latestSnapshot.risk_approved_count.toLocaleString()}</div>
            <div className="text-gray-500">Risk Rejected</div>
            <div className="text-rose-400 font-mono text-right">{latestSnapshot.risk_rejected_count.toLocaleString()}</div>
            <div className="text-gray-500">Shadow Approved</div>
            <div className="text-emerald-400 font-mono text-right">{latestSnapshot.shadow_approved_count.toLocaleString()}</div>
            <div className="text-gray-500">Shadow Blocked</div>
            <div className="text-rose-400 font-mono text-right">{latestSnapshot.shadow_blocked_count.toLocaleString()}</div>
            <div className="text-gray-500">Unique Wallets</div>
            <div className="text-white font-mono text-right">{latestSnapshot.unique_wallets.toLocaleString()}</div>
            <div className="text-gray-500">Unique Markets</div>
            <div className="text-white font-mono text-right">{latestSnapshot.unique_markets.toLocaleString()}</div>
          </div>
        </div>
      )}
    </div>
  );
}
