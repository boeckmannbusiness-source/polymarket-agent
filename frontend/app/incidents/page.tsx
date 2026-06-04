"use client";

import { useState, useEffect, useCallback } from "react";
import { IncidentPanel } from "@/components/IncidentPanel";
import { LiveIndicator } from "@/components/LiveIndicator";

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const fetchIncidents = useCallback(async () => {
    try {
      const res = await fetch("/api/v1/incidents");
      const data = await res.json();
      setIncidents(data.incidents || []);
      setStats(data.stats || null);
    } catch {
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchIncidents(); }, [fetchIncidents]);

  const handleResolve = async (id: string) => {
    await fetch(`/api/v1/incidents/${id}/resolve`, { method: "POST" });
    fetchIncidents();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Incidents</h1>
          <p className="text-[10px] text-gray-500 uppercase tracking-wider">Operational incident management</p>
        </div>
      </div>

      {stats && (
        <div className="grid grid-cols-5 gap-3">
          {[
            { label: "Total", value: stats.total, color: "text-white" },
            { label: "Open", value: stats.open, color: "text-red-400" },
            { label: "Investigating", value: stats.investigating, color: "text-amber-400" },
            { label: "Mitigated", value: stats.mitigated, color: "text-blue-400" },
            { label: "Resolved", value: stats.resolved, color: "text-emerald-400" },
          ].map((s) => (
            <div key={s.label} className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3 text-center">
              <div className={`text-2xl font-bold font-mono ${s.color}`}>{s.value}</div>
              <div className="text-[10px] text-muted-foreground uppercase mt-1">{s.label}</div>
            </div>
          ))}
        </div>
      )}

      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
          Incident Feed
        </h2>
        <IncidentPanel incidents={incidents} onResolve={handleResolve} loading={loading} />
      </div>
    </div>
  );
}
