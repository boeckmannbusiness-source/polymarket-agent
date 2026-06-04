"use client";

import { useState, useEffect, useCallback } from "react";
import { api, RedisStatus } from "@/lib/api";
import { Server, HardDrive, Key, Clock, TrendingUp } from "lucide-react";

function utilizationColor(pct: number): string {
  if (pct >= 95) return "bg-red-500";
  if (pct >= 85) return "bg-orange-500";
  if (pct >= 75) return "bg-yellow-500";
  return "bg-emerald-500";
}

function utilizationTextColor(pct: number): string {
  if (pct >= 85) return "text-red-500";
  if (pct >= 75) return "text-yellow-500";
  return "text-emerald-500";
}

export function RedisHealthWidget() {
  const [status, setStatus] = useState<RedisStatus | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await api.system.redis();
      setStatus(data);
    } catch {}
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 10000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  if (!status) {
    return (
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <div className="flex items-center gap-2 mb-3">
          <Server className="h-3.5 w-3.5 text-gray-500" />
          <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Redis Health</h3>
        </div>
        <div className="h-16 animate-pulse rounded bg-gray-800" />
      </div>
    );
  }

  const barColor = utilizationColor(status.utilization_percent);
  const textColor = utilizationTextColor(status.utilization_percent);
  const keysWithTTLPct = status.key_count > 0
    ? ((status.keys_with_expiry / status.key_count) * 100).toFixed(1)
    : "0.0";

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Server className="h-3.5 w-3.5 text-gray-500" />
          <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Redis Health</h3>
        </div>
        <span className={`text-[10px] font-bold font-mono ${textColor}`}>
          {status.utilization_percent.toFixed(1)}%
        </span>
      </div>

      {/* Memory bar */}
      <div className="mb-3">
        <div className="flex justify-between text-[10px] text-gray-500 mb-1">
          <span>Memory</span>
          <span className="font-mono">
            {status.used_memory_mb.toFixed(1)} MB / {status.maxmemory_mb.toFixed(0)} MB
          </span>
        </div>
        <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${barColor}`}
            style={{ width: `${Math.min(status.utilization_percent, 100)}%` }}
          />
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-2 text-[10px]">
        <div className="flex items-center gap-1.5">
          <HardDrive className="h-3 w-3 text-gray-500 shrink-0" />
          <span className="text-gray-400">Peak:</span>
          <span className="font-mono text-white">{status.peak_memory_mb.toFixed(1)} MB</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Key className="h-3 w-3 text-gray-500 shrink-0" />
          <span className="text-gray-400">Keys:</span>
          <span className="font-mono text-white">{status.key_count.toLocaleString()}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <TrendingUp className="h-3 w-3 text-gray-500 shrink-0" />
          <span className="text-gray-400">With TTL:</span>
          <span className="font-mono text-white">{keysWithTTLPct}%</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Clock className="h-3 w-3 text-gray-500 shrink-0" />
          <span className="text-gray-400">Avg TTL:</span>
          <span className="font-mono text-white">
            {status.avg_ttl_seconds > 0
              ? `${(status.avg_ttl_seconds / 60).toFixed(0)}m`
              : "N/A"}
          </span>
        </div>
      </div>
    </div>
  );
}
