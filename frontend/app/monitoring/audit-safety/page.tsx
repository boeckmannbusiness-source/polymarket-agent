"use client";

import { useState } from "react";
import { useSystemSafety, useDataIntegrity, useFeedbackCycles, useStressSafety, useReadiness } from "@/lib/hooks";
import { api } from "@/lib/api";
import { StatCard } from "@/components/StatCard";
import {
  Activity, Shield, AlertTriangle, CheckCircle, XCircle,
  Radio, GitBranch, BarChart3, Gauge, TrendingUp, Zap,
  Cpu, Server, Layers, Eye, AlertOctagon,
} from "lucide-react";

type Tab = "system" | "data" | "cycles" | "stress" | "readiness";

const CLASSIFICATION_COLORS: Record<string, string> = {
  NOT_READY: "text-red-400 bg-red-500/10 border-red-500/30",
  PAPER_READY: "text-amber-400 bg-amber-500/10 border-amber-500/30",
  MICRO_CAPITAL_READY: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
  LIVE_READY: "text-blue-400 bg-blue-500/10 border-blue-500/30",
};

const CLASSIFICATION_ICONS: Record<string, any> = {
  NOT_READY: XCircle,
  PAPER_READY: AlertTriangle,
  MICRO_CAPITAL_READY: CheckCircle,
  LIVE_READY: Zap,
};

export default function AuditSafetyPage() {
  const [tab, setTab] = useState<Tab>("readiness");
  const [running, setRunning] = useState(false);
  const { data: systemData, loading: sysLoading, refetch: refetchSys } = useSystemSafety();
  const { data: dataData, loading: dataLoading, refetch: refetchData } = useDataIntegrity();
  const { data: cyclesData, loading: cyclesLoading, refetch: refetchCycles } = useFeedbackCycles();
  const { data: stressData, loading: stressLoading, refetch: refetchStress } = useStressSafety();
  const { data: readinessData, loading: readinessLoading, refetch: refetchReadiness } = useReadiness();

  const handleRunAudit = async () => {
    setRunning(true);
    try {
      await api.audit.run();
      refetchSys();
      refetchData();
      refetchCycles();
      refetchStress();
      refetchReadiness();
    } catch (e) {
      console.error("Audit run failed", e);
    } finally {
      setRunning(false);
    }
  };

  const tabs: { key: Tab; label: string; icon: React.ReactNode }[] = [
    { key: "readiness", label: "Deployment Gate", icon: <Shield className="h-3 w-3" /> },
    { key: "system", label: "System Safety", icon: <Server className="h-3 w-3" /> },
    { key: "data", label: "Data Health", icon: <BarChart3 className="h-3 w-3" /> },
    { key: "cycles", label: "Cycle Risk", icon: <GitBranch className="h-3 w-3" /> },
    { key: "stress", label: "Stress Test", icon: <Activity className="h-3 w-3" /> },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Audit & Safety</h1>
          <p className="text-[10px] text-gray-500 uppercase tracking-wider">
            Production safety gate — no execution logic
          </p>
        </div>
        <button
          onClick={handleRunAudit}
          disabled={running}
          className="text-[10px] px-3 py-1.5 border border-border rounded hover:border-gray-500 transition-colors disabled:opacity-50 flex items-center gap-1.5"
        >
          <Activity className="h-3 w-3" />
          {running ? "Running..." : "Run Full Audit"}
        </button>
      </div>

      {/* Readiness gate at top always visible */}
      {readinessData && (
        <div className={`rounded-xl border p-4 ${
          readinessData.classification === "NOT_READY" ? "border-red-500/30 bg-red-950/10" :
          readinessData.classification === "PAPER_READY" ? "border-amber-500/30 bg-amber-950/10" :
          readinessData.classification === "MICRO_CAPITAL_READY" ? "border-emerald-500/30 bg-emerald-950/10" :
          "border-blue-500/30 bg-blue-950/10"
        }`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-full ${
                readinessData.classification === "NOT_READY" ? "bg-red-500/20" :
                readinessData.classification === "PAPER_READY" ? "bg-amber-500/20" :
                readinessData.classification === "MICRO_CAPITAL_READY" ? "bg-emerald-500/20" :
                "bg-blue-500/20"
              }`}>
                {(() => {
                  const Icon = CLASSIFICATION_ICONS[readinessData.classification] || AlertOctagon;
                  return <Icon className={`h-5 w-5 ${
                    readinessData.classification === "NOT_READY" ? "text-red-400" :
                    readinessData.classification === "PAPER_READY" ? "text-amber-400" :
                    readinessData.classification === "MICRO_CAPITAL_READY" ? "text-emerald-400" :
                    "text-blue-400"
                  }`} />;
                })()}
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-400 uppercase tracking-wider">Deployment Classification:</span>
                  <span className={`text-sm font-bold px-2 py-0.5 rounded border ${
                    CLASSIFICATION_COLORS[readinessData.classification] || "text-gray-400"
                  }`}>
                    {readinessData.classification}
                  </span>
                </div>
                <p className="text-xs text-gray-500 mt-1">{readinessData.recommendation}</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-center">
                <div className="relative w-16 h-16">
                  <svg className="w-16 h-16 -rotate-90" viewBox="0 0 64 64">
                    <circle cx="32" cy="32" r="28" fill="none" stroke="rgb(31,41,55)" strokeWidth="4" />
                    <circle cx="32" cy="32" r="28" fill="none" stroke={
                      readinessData.overall_score >= 80 ? "rgb(96,165,250)" :
                      readinessData.overall_score >= 65 ? "rgb(52,211,153)" :
                      readinessData.overall_score >= 40 ? "rgb(251,191,36)" :
                      "rgb(239,68,68)"
                    } strokeWidth="4" strokeDasharray={`${(readinessData.overall_score / 100) * 176} 176`} strokeLinecap="round" />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-sm font-bold font-mono text-white">{readinessData.overall_score.toFixed(0)}</span>
                  </div>
                </div>
                <div className="text-[9px] text-gray-500 mt-0.5">Overall</div>
              </div>
            </div>
          </div>
          <div className="mt-3 flex items-center gap-2 text-[10px]">
            <span className="text-gray-500">Stability: {readinessData.stability_score.toFixed(0)}</span>
            <span className="text-gray-600">|</span>
            <span className="text-gray-500">Data: {readinessData.data_score.toFixed(0)}</span>
            <span className="text-gray-600">|</span>
            <span className="text-gray-500">Stress: {readinessData.stress_score.toFixed(0)}</span>
            {readinessData.classification === "MICRO_CAPITAL_READY" && (
              <span className="ml-2 text-emerald-400 font-bold">SAFE FOR 50-100€ LIVE TEST</span>
            )}
            {readinessData.classification === "NOT_READY" && (
              <span className="ml-2 text-red-400 font-bold">NOT SAFE FOR LIVE CAPITAL</span>
            )}
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[var(--border)] pb-2 overflow-x-auto">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex items-center gap-1.5 text-[10px] uppercase tracking-wider px-3 py-1.5 rounded-t transition-colors whitespace-nowrap ${
              tab === t.key
                ? "text-white border-b-2 border-[var(--primary)]"
                : "text-gray-500 hover:text-gray-300"
            }`}
          >
            {t.icon}
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Tab: System Safety ──────────────────────── */}
      {tab === "system" && (
        <div className="space-y-4">
          {sysLoading && <div className="text-center py-8 text-xs text-muted-foreground">Analyzing system architecture...</div>}
          {!sysLoading && systemData && (
            <>
              {/* Component count summary */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <StatCard title="Total Components" value={`${systemData.components?.length || 0}`} icon={Cpu} loading={sysLoading} />
                <StatCard title="Critical Paths" value={`${systemData.critical_paths?.length || 0}`} icon={GitBranch} loading={sysLoading} />
                <StatCard title="SPOFs" value={`${systemData.single_points_of_failure?.length || 0}`} icon={AlertTriangle}
                  color={(systemData.single_points_of_failure?.length || 0) > 0 ? "negative" : "positive"} loading={sysLoading} />
                <StatCard title="Risk Flags" value={`${systemData.risk_flags?.length || 0}`} icon={AlertOctagon}
                  color={(systemData.risk_flags?.length || 0) > 0 ? "negative" : "default"} loading={sysLoading} />
              </div>

              {/* Components table */}
              <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
                  <Server className="h-3.5 w-3.5 inline mr-1" />
                  Component Classification
                </h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-gray-800 text-[10px] text-gray-500 uppercase tracking-wider">
                        <th className="text-left py-2 pr-2">Component</th>
                        <th className="text-center py-2 pr-2">Classification</th>
                        <th className="text-left py-2 pr-2">Dependencies</th>
                      </tr>
                    </thead>
                    <tbody>
                      {systemData.components?.map((c: any) => (
                        <tr key={c.name} className="border-b border-gray-900 hover:bg-gray-900/30">
                          <td className="py-2 pr-2 text-gray-300 font-medium">{c.name}</td>
                          <td className="py-2 pr-2 text-center">
                            <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                              c.classification === "deterministic" ? "bg-blue-500/10 text-blue-400" :
                              c.classification === "stochastic" ? "bg-purple-500/10 text-purple-400" :
                              "bg-amber-500/10 text-amber-400"
                            }`}>
                              {c.classification.toUpperCase()}
                            </span>
                          </td>
                          <td className="py-2 pr-2 text-gray-400 text-[10px]">{(c.depends_on || []).join(", ") || "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Critical paths */}
              {systemData.critical_paths?.length > 0 && (
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                  <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
                    <GitBranch className="h-3.5 w-3.5 inline mr-1" />
                    Critical Paths
                  </h2>
                  <div className="space-y-2">
                    {systemData.critical_paths.map((cp: any, i: number) => (
                      <div key={i} className="flex items-center gap-2 py-2 border-b border-gray-900 text-xs">
                        <span className="text-gray-500 font-mono text-[10px]">#{i + 1}</span>
                        <span className="text-gray-300">{cp.path?.join(" → ")}</span>
                        <span className="text-gray-500 text-[10px]">({cp.length} hops)</span>
                        {cp.length > 3 && <span className="text-red-400 text-[10px] font-bold">DEEP</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* SPOFs */}
              {systemData.single_points_of_failure?.length > 0 && (
                <div className="rounded-xl border border-red-500/20 bg-red-950/10 p-4">
                  <h2 className="text-[10px] font-bold text-red-400 uppercase tracking-widest mb-4">
                    <AlertTriangle className="h-3.5 w-3.5 inline mr-1" />
                    Single Points of Failure
                  </h2>
                  <div className="space-y-2">
                    {systemData.single_points_of_failure.map((spof: any, i: number) => (
                      <div key={i} className="flex items-center justify-between py-2 border-b border-red-900/30 text-xs">
                        <span className="text-gray-300 font-medium">{spof.component}</span>
                        <div className="flex items-center gap-3 text-gray-400">
                          <span>{spof.reason}</span>
                          <span className="text-red-400 font-mono">{spof.downstream_count} dependents</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Risk flags */}
              {systemData.risk_flags?.length > 0 && (
                <div className="rounded-xl border border-amber-500/20 bg-amber-950/10 p-4">
                  <h2 className="text-[10px] font-bold text-amber-400 uppercase tracking-widest mb-4">
                    <AlertOctagon className="h-3.5 w-3.5 inline mr-1" />
                    Risk Flags
                  </h2>
                  <div className="space-y-1">
                    {systemData.risk_flags.map((flag: string, i: number) => (
                      <div key={i} className="flex items-start gap-2 py-1 text-xs">
                        <span className="text-amber-400 mt-0.5">!</span>
                        <span className="text-gray-300">{flag}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
          {!sysLoading && !systemData && (
            <div className="text-center py-8 text-xs text-muted-foreground">Run an audit to see system safety data.</div>
          )}
        </div>
      )}

      {/* ── Tab: Data Health ─────────────────────────── */}
      {tab === "data" && (
        <div className="space-y-4">
          {dataLoading && <div className="text-center py-8 text-xs text-muted-foreground">Validating data integrity...</div>}
          {!dataLoading && dataData && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <StatCard title="Overall Data Quality" value={`${dataData.overall_data_quality_score.toFixed(1)}/100`} icon={Gauge}
                  color={dataData.overall_data_quality_score >= 65 ? "positive" : dataData.overall_data_quality_score >= 40 ? "default" : "negative"} />
                <StatCard title="Signal Sources" value={`${dataData.signals?.length || 0}`} icon={Layers} />
                <StatCard title="Risk Flags" value={`${dataData.risk_flags?.length || 0}`} icon={AlertTriangle}
                  color={(dataData.risk_flags?.length || 0) > 0 ? "negative" : "positive"} />
              </div>

              <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
                  <BarChart3 className="h-3.5 w-3.5 inline mr-1" />
                  Signal Health Scores
                </h2>
                <div className="space-y-3">
                  {dataData.signals?.map((sig: any) => (
                    <div key={sig.source} className="space-y-1">
                      <div className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-2">
                          <span className="text-gray-300 font-medium">{sig.source}</span>
                          <span className={`text-[9px] px-1 py-0.5 rounded ${
                            sig.source_type === "internal_computed" ? "bg-blue-500/10 text-blue-400" :
                            sig.source_type === "external_derived" ? "bg-purple-500/10 text-purple-400" :
                            sig.source_type === "synthetic" ? "bg-amber-500/10 text-amber-400" :
                            "bg-gray-500/10 text-gray-400"
                          }`}>
                            {sig.source_type.replace(/_/g, " ").toUpperCase()}
                          </span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="text-gray-500 text-[10px]">{sig.freshness_hours.toFixed(0)}h old</span>
                          <span className="text-gray-500 text-[10px]">miss: {sig.missingness_pct.toFixed(0)}%</span>
                          <span className={`font-mono font-bold ${
                            sig.health_score >= 65 ? "text-emerald-400" :
                            sig.health_score >= 40 ? "text-amber-400" : "text-red-400"
                          }`}>{sig.health_score.toFixed(0)}</span>
                        </div>
                      </div>
                      <div className="w-full h-1.5 bg-gray-800 rounded-full overflow-hidden">
                        <div className={`h-full rounded-full ${
                          sig.health_score >= 65 ? "bg-emerald-500" :
                          sig.health_score >= 40 ? "bg-amber-500" : "bg-red-500"
                        }`} style={{ width: `${sig.health_score}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {dataData.risk_flags?.length > 0 && (
                <div className="rounded-xl border border-red-500/20 bg-red-950/10 p-4">
                  <h2 className="text-[10px] font-bold text-red-400 uppercase tracking-widest mb-4">
                    <AlertTriangle className="h-3.5 w-3.5 inline mr-1" />
                    Data Risk Flags
                  </h2>
                  <div className="space-y-1">
                    {dataData.risk_flags.map((flag: string, i: number) => (
                      <div key={i} className="flex items-start gap-2 py-1 text-xs">
                        <span className="text-red-400 mt-0.5">!</span>
                        <span className="text-gray-300">{flag}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
          {!dataLoading && !dataData && (
            <div className="text-center py-8 text-xs text-muted-foreground">Run an audit to see data integrity data.</div>
          )}
        </div>
      )}

      {/* ── Tab: Cycle Risk ──────────────────────────── */}
      {tab === "cycles" && (
        <div className="space-y-4">
          {cyclesLoading && <div className="text-center py-8 text-xs text-muted-foreground">Checking for feedback cycles...</div>}
          {!cyclesLoading && cyclesData && (
            <>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                <StatCard title="Overall Risk" value={cyclesData.overall_risk_level} icon={GitBranch}
                  color={cyclesData.overall_risk_level === "HIGH" ? "negative" : cyclesData.overall_risk_level === "MEDIUM" ? "default" : "positive"} />
                <StatCard title="Cycles Detected" value={`${cyclesData.cycles?.length || 0}`} icon={AlertOctagon}
                  color={(cyclesData.cycles?.length || 0) > 0 ? "negative" : "positive"} />
                <StatCard title="Risk Flags" value={`${cyclesData.risk_flags?.length || 0}`} icon={AlertTriangle}
                  color={(cyclesData.risk_flags?.length || 0) > 0 ? "negative" : "positive"} />
              </div>

              {cyclesData.cycles?.length > 0 ? (
                <div className="rounded-xl border border-red-500/20 bg-red-950/10 p-4">
                  <h2 className="text-[10px] font-bold text-red-400 uppercase tracking-widest mb-4">
                    <GitBranch className="h-3.5 w-3.5 inline mr-1" />
                    Detected Feedback Cycles
                  </h2>
                  <div className="space-y-3">
                    {cyclesData.cycles.map((cycle: any, i: number) => (
                      <div key={i} className="border border-red-900/30 rounded-lg p-3">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs text-gray-300 font-mono">
                            {cycle.cycle?.join(" → ")}
                          </span>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${
                            cycle.risk_level === "HIGH" ? "bg-red-500/10 text-red-400" :
                            cycle.risk_level === "MEDIUM" ? "bg-amber-500/10 text-amber-400" :
                            "bg-emerald-500/10 text-emerald-400"
                          }`}>
                            {cycle.risk_level}
                          </span>
                        </div>
                        <div className="text-[10px] text-gray-500">
                          Length: {cycle.cycle_length} hops
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="rounded-xl border border-emerald-500/20 bg-emerald-950/10 p-4">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="h-4 w-4 text-emerald-400" />
                    <span className="text-xs text-emerald-400">No cycles detected — dependency graph is acyclic</span>
                  </div>
                </div>
              )}

              {cyclesData.risk_flags?.map((flag: string, i: number) => (
                flag.includes("No cycles") ? null : (
                  <div key={i} className="flex items-start gap-2 py-1 text-xs text-gray-300">
                    <span className="text-amber-400 mt-0.5">!</span>
                    <span>{flag}</span>
                  </div>
                )
              ))}
            </>
          )}
          {!cyclesLoading && !cyclesData && (
            <div className="text-center py-8 text-xs text-muted-foreground">Run an audit to check for feedback cycles.</div>
          )}
        </div>
      )}

      {/* ── Tab: Stress Test ─────────────────────────── */}
      {tab === "stress" && (
        <div className="space-y-4">
          {stressLoading && <div className="text-center py-8 text-xs text-muted-foreground">Simulating stress scenarios...</div>}
          {!stressLoading && stressData && (
            <>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                <StatCard title="Stress Score" value={`${stressData.overall_stress_score.toFixed(0)}/100`} icon={Gauge}
                  color={stressData.overall_stress_score >= 65 ? "positive" : stressData.overall_stress_score >= 40 ? "default" : "negative"} />
                <StatCard title="Scenarios" value={`${stressData.scenario_results?.length || 0}/3`} icon={Activity} />
                <StatCard title="Worst Case" value={stressData.worst_case_scenario || "-"} icon={AlertTriangle}
                  color="negative" />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {stressData.scenario_results?.map((scenario: any) => {
                  const isWorst = scenario.scenario_type === stressData.worst_case_scenario;
                  return (
                    <div key={scenario.scenario_id} className={`rounded-xl border p-4 ${
                      isWorst ? "border-red-500/30 bg-red-950/10" : "border-[var(--border)] bg-[var(--card)]"
                    }`}>
                      <div className="flex items-center justify-between mb-3">
                        <h3 className={`text-xs font-bold ${isWorst ? "text-red-400" : "text-white"}`}>
                          {scenario.scenario_type}
                        </h3>
                        {isWorst && <span className="text-[9px] px-1.5 py-0.5 rounded bg-red-500/10 text-red-400 font-bold">WORST</span>}
                      </div>
                      <div className="space-y-2">
                        <div className="flex justify-between text-[10px]">
                          <span className="text-gray-500">Drawdown Estimate</span>
                          <span className={`font-mono font-bold ${scenario.max_drawdown_estimate > 15 ? "text-red-400" : "text-amber-400"}`}>
                            {scenario.max_drawdown_estimate.toFixed(1)}%
                          </span>
                        </div>
                        <div className="flex justify-between text-[10px]">
                          <span className="text-gray-500">Allocation Deviation</span>
                          <span className="font-mono text-gray-300">{scenario.allocation_deviation.toFixed(4)}</span>
                        </div>
                        <div className="flex justify-between text-[10px]">
                          <span className="text-gray-500">Recovery Sensitivity</span>
                          <span className={`font-mono ${
                            scenario.recovery_sensitivity === "high" ? "text-red-400" :
                            scenario.recovery_sensitivity === "medium" ? "text-amber-400" : "text-emerald-400"
                          }`}>{scenario.recovery_sensitivity.toUpperCase()}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {stressData.risk_flags?.length > 0 && (
                <div className="rounded-xl border border-red-500/20 bg-red-950/10 p-4">
                  <h2 className="text-[10px] font-bold text-red-400 uppercase tracking-widest mb-4">
                    <AlertTriangle className="h-3.5 w-3.5 inline mr-1" />
                    Stress Risk Flags
                  </h2>
                  <div className="space-y-1">
                    {stressData.risk_flags.map((flag: string, i: number) => (
                      <div key={i} className="flex items-start gap-2 py-1 text-xs">
                        <span className="text-red-400 mt-0.5">!</span>
                        <span className="text-gray-300">{flag}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
          {!stressLoading && !stressData && (
            <div className="text-center py-8 text-xs text-muted-foreground">Run an audit to see stress test results.</div>
          )}
        </div>
      )}

      {/* ── Tab: Readiness (detailed) ────────────────── */}
      {tab === "readiness" && (
        <div className="space-y-4">
          {readinessLoading && <div className="text-center py-8 text-xs text-muted-foreground">Evaluating readiness...</div>}
          {!readinessLoading && readinessData && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                  <h3 className="text-[9px] text-gray-500 uppercase tracking-wider mb-2">Stability Score</h3>
                  <div className="flex items-center gap-3">
                    <div className="relative w-12 h-12">
                      <svg className="w-12 h-12 -rotate-90" viewBox="0 0 36 36">
                        <circle cx="18" cy="18" r="15.5" fill="none" stroke="#1f2937" strokeWidth="3" />
                        <circle cx="18" cy="18" r="15.5" fill="none" stroke={
                          readinessData.stability_score >= 65 ? "#10b981" : readinessData.stability_score >= 40 ? "#f59e0b" : "#ef4444"
                        } strokeWidth="3" strokeDasharray={`${(readinessData.stability_score / 100) * 97.4} 97.4`} />
                      </svg>
                      <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-white">
                        {readinessData.stability_score.toFixed(0)}
                      </span>
                    </div>
                    <div className="text-[10px] text-gray-400">
                      <div>Dependency simplicity</div>
                      <div>Cycle risk</div>
                    </div>
                  </div>
                </div>
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                  <h3 className="text-[9px] text-gray-500 uppercase tracking-wider mb-2">Data Score</h3>
                  <div className="flex items-center gap-3">
                    <div className="relative w-12 h-12">
                      <svg className="w-12 h-12 -rotate-90" viewBox="0 0 36 36">
                        <circle cx="18" cy="18" r="15.5" fill="none" stroke="#1f2937" strokeWidth="3" />
                        <circle cx="18" cy="18" r="15.5" fill="none" stroke={
                          readinessData.data_score >= 65 ? "#10b981" : readinessData.data_score >= 40 ? "#f59e0b" : "#ef4444"
                        } strokeWidth="3" strokeDasharray={`${(readinessData.data_score / 100) * 97.4} 97.4`} />
                      </svg>
                      <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-white">
                        {readinessData.data_score.toFixed(0)}
                      </span>
                    </div>
                    <div className="text-[10px] text-gray-400">
                      <div>Signal quality</div>
                      <div>Data freshness</div>
                    </div>
                  </div>
                </div>
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                  <h3 className="text-[9px] text-gray-500 uppercase tracking-wider mb-2">Stress Score</h3>
                  <div className="flex items-center gap-3">
                    <div className="relative w-12 h-12">
                      <svg className="w-12 h-12 -rotate-90" viewBox="0 0 36 36">
                        <circle cx="18" cy="18" r="15.5" fill="none" stroke="#1f2937" strokeWidth="3" />
                        <circle cx="18" cy="18" r="15.5" fill="none" stroke={
                          readinessData.stress_score >= 65 ? "#10b981" : readinessData.stress_score >= 40 ? "#f59e0b" : "#ef4444"
                        } strokeWidth="3" strokeDasharray={`${(readinessData.stress_score / 100) * 97.4} 97.4`} />
                      </svg>
                      <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-white">
                        {readinessData.stress_score.toFixed(0)}
                      </span>
                    </div>
                    <div className="text-[10px] text-gray-400">
                      <div>Worst-case impact</div>
                      <div>Recovery sensitivity</div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
                  <Eye className="h-3.5 w-3.5 inline mr-1" />
                  Risk Summary
                </h2>
                <p className="text-xs text-gray-300 leading-relaxed">{readinessData.risk_summary}</p>
              </div>

              <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
                  <Shield className="h-3.5 w-3.5 inline mr-1" />
                  Recommendation
                </h2>
                <div className={`p-3 rounded-lg border text-xs ${
                  readinessData.classification === "NOT_READY" ? "border-red-500/30 bg-red-950/10 text-red-300" :
                  readinessData.classification === "PAPER_READY" ? "border-amber-500/30 bg-amber-950/10 text-amber-300" :
                  readinessData.classification === "MICRO_CAPITAL_READY" ? "border-emerald-500/30 bg-emerald-950/10 text-emerald-300" :
                  "border-blue-500/30 bg-blue-950/10 text-blue-300"
                }`}>
                  {readinessData.recommendation}
                </div>
              </div>
            </>
          )}
          {!readinessLoading && !readinessData && (
            <div className="text-center py-8 text-xs text-muted-foreground">Run an audit to see readiness evaluation.</div>
          )}
        </div>
      )}
    </div>
  );
}
