"use client";

import { useState } from "react";
import { useExecutionSafety, useCapitalProtection, useFailClosed, useRuntimeEnforcement, useOperationalReadiness, useMicroCapitalReadiness } from "@/lib/hooks";
import { api } from "@/lib/api";
import { StatCard } from "@/components/StatCard";
import {
  Activity, Shield, AlertTriangle, CheckCircle, XCircle,
  Radio, GitBranch, BarChart3, Gauge, Zap,
  Cpu, Server, Layers, Eye, AlertOctagon, Lock, Unlock, Wifi,
  Sliders, ClipboardList,
} from "lucide-react";

type Tab = "readiness" | "execution" | "capital" | "failclosed" | "runtime" | "operational";

const CLASSIFICATION_COLORS: Record<string, string> = {
  NOT_READY: "text-red-400 bg-red-500/10 border-red-500/30",
  PAPER_READY: "text-amber-400 bg-amber-500/10 border-amber-500/30",
  MICRO_CAPITAL_READY: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
};

const CLASSIFICATION_ICONS: Record<string, any> = {
  NOT_READY: XCircle,
  PAPER_READY: AlertTriangle,
  MICRO_CAPITAL_READY: CheckCircle,
};

export default function MicroCapitalReadinessPage() {
  const [tab, setTab] = useState<Tab>("readiness");
  const [running, setRunning] = useState(false);
  const { data: execData, loading: execLoading, refetch: refetchExec } = useExecutionSafety();
  const { data: capData, loading: capLoading, refetch: refetchCap } = useCapitalProtection();
  const { data: fcData, loading: fcLoading, refetch: refetchFc } = useFailClosed();
  const { data: rtData, loading: rtLoading, refetch: refetchRt } = useRuntimeEnforcement();
  const { data: opData, loading: opLoading, refetch: refetchOp } = useOperationalReadiness();
  const { data: readinessData, loading: readinessLoading, refetch: refetchReadiness } = useMicroCapitalReadiness();

  const handleRunAudit = async () => {
    setRunning(true);
    try {
      await api.microCapital.run();
      refetchExec();
      refetchCap();
      refetchFc();
      refetchRt();
      refetchOp();
      refetchReadiness();
    } catch (e) {
      console.error("Micro-capital audit run failed", e);
    } finally {
      setRunning(false);
    }
  };

  const tabs: { key: Tab; label: string; icon: React.ReactNode }[] = [
    { key: "readiness", label: "Deployment Gate", icon: <Shield className="h-3 w-3" /> },
    { key: "execution", label: "Execution Safety", icon: <Cpu className="h-3 w-3" /> },
    { key: "capital", label: "Capital Protection", icon: <Lock className="h-3 w-3" /> },
    { key: "failclosed", label: "Fail-Closed", icon: <Wifi className="h-3 w-3" /> },
    { key: "runtime", label: "Runtime Enforcement", icon: <Sliders className="h-3 w-3" /> },
    { key: "operational", label: "Operational Readiness", icon: <ClipboardList className="h-3 w-3" /> },
  ];

  const scoreColor = (s: number) =>
    s >= 85 ? "text-emerald-400" : s >= 70 ? "text-amber-400" : "text-red-400";

  const bgScoreColor = (s: number) =>
    s >= 85 ? "border-emerald-500/30 bg-emerald-950/10" :
    s >= 70 ? "border-amber-500/30 bg-amber-950/10" :
    "border-red-500/30 bg-red-950/10";

  const gaugeColor = (s: number) =>
    s >= 85 ? "#10b981" : s >= 70 ? "#f59e0b" : "#ef4444";

  const gaugeDash = (s: number) => `${(s / 100) * 97.4} 97.4`;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Micro-Capital Readiness</h1>
          <p className="text-[10px] text-gray-500 uppercase tracking-wider">
            Phase 0.5 Runtime Safety Audit — 25-100€ live test qualification
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
        <div className={`rounded-xl border p-4 ${bgScoreColor(readinessData.overall_score)}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-full ${
                readinessData.classification === "NOT_READY" ? "bg-red-500/20" :
                readinessData.classification === "PAPER_READY" ? "bg-amber-500/20" :
                "bg-emerald-500/20"
              }`}>
                {(() => {
                  const Icon = CLASSIFICATION_ICONS[readinessData.classification] || AlertOctagon;
                  return <Icon className={`h-5 w-5 ${
                    readinessData.classification === "NOT_READY" ? "text-red-400" :
                    readinessData.classification === "PAPER_READY" ? "text-amber-400" :
                    "text-emerald-400"
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
                    <circle cx="32" cy="32" r="28" fill="none" stroke={gaugeColor(readinessData.overall_score)}
                      strokeWidth="4" strokeDasharray={`${(readinessData.overall_score / 100) * 176} 176`} strokeLinecap="round" />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-sm font-bold font-mono text-white">{readinessData.overall_score.toFixed(0)}</span>
                  </div>
                </div>
                <div className="text-[9px] text-gray-500 mt-0.5">Overall</div>
              </div>
            </div>
          </div>
          <div className="mt-3 flex items-center gap-2 text-[10px] flex-wrap">
            <span className="text-gray-500">Execution: <span className={scoreColor(readinessData.execution_safety_score)}>{readinessData.execution_safety_score.toFixed(0)}</span></span>
            <span className="text-gray-600">|</span>
            <span className="text-gray-500">Capital: <span className={scoreColor(readinessData.capital_protection_score)}>{readinessData.capital_protection_score.toFixed(0)}</span></span>
            <span className="text-gray-600">|</span>
            <span className="text-gray-500">Fail-Closed: <span className={scoreColor(readinessData.fail_closed_score)}>{readinessData.fail_closed_score.toFixed(0)}</span></span>
            <span className="text-gray-600">|</span>
            <span className="text-gray-500">Runtime: <span className={scoreColor(readinessData.runtime_enforcement_score)}>{readinessData.runtime_enforcement_score.toFixed(0)}</span></span>
            <span className="text-gray-600">|</span>
            <span className="text-gray-500">Operational: <span className={scoreColor(readinessData.operational_readiness_score)}>{readinessData.operational_readiness_score.toFixed(0)}</span></span>
            {readinessData.classification === "MICRO_CAPITAL_READY" && (
              <span className="ml-2 text-emerald-400 font-bold">SAFE FOR 25-100€ LIVE TEST</span>
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

      {/* ── Tab: Readiness (Detail) ─────────────── */}
      {tab === "readiness" && (
        <div className="space-y-4">
          {readinessLoading && <div className="text-center py-8 text-xs text-muted-foreground">Evaluating micro-capital readiness...</div>}
          {!readinessLoading && readinessData && (
            <>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3 text-center">
                  <div className="relative w-12 h-12 mx-auto mb-2">
                    <svg className="w-12 h-12 -rotate-90" viewBox="0 0 36 36">
                      <circle cx="18" cy="18" r="15.5" fill="none" stroke="#1f2937" strokeWidth="3" />
                      <circle cx="18" cy="18" r="15.5" fill="none" stroke={gaugeColor(readinessData.execution_safety_score)}
                        strokeWidth="3" strokeDasharray={gaugeDash(readinessData.execution_safety_score)} />
                    </svg>
                    <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-white">
                      {readinessData.execution_safety_score.toFixed(0)}
                    </span>
                  </div>
                  <div className="text-[9px] text-gray-400">Execution Safety</div>
                </div>
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3 text-center">
                  <div className="relative w-12 h-12 mx-auto mb-2">
                    <svg className="w-12 h-12 -rotate-90" viewBox="0 0 36 36">
                      <circle cx="18" cy="18" r="15.5" fill="none" stroke="#1f2937" strokeWidth="3" />
                      <circle cx="18" cy="18" r="15.5" fill="none" stroke={gaugeColor(readinessData.capital_protection_score)}
                        strokeWidth="3" strokeDasharray={gaugeDash(readinessData.capital_protection_score)} />
                    </svg>
                    <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-white">
                      {readinessData.capital_protection_score.toFixed(0)}
                    </span>
                  </div>
                  <div className="text-[9px] text-gray-400">Capital Protection</div>
                </div>
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3 text-center">
                  <div className="relative w-12 h-12 mx-auto mb-2">
                    <svg className="w-12 h-12 -rotate-90" viewBox="0 0 36 36">
                      <circle cx="18" cy="18" r="15.5" fill="none" stroke="#1f2937" strokeWidth="3" />
                      <circle cx="18" cy="18" r="15.5" fill="none" stroke={gaugeColor(readinessData.fail_closed_score)}
                        strokeWidth="3" strokeDasharray={gaugeDash(readinessData.fail_closed_score)} />
                    </svg>
                    <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-white">
                      {readinessData.fail_closed_score.toFixed(0)}
                    </span>
                  </div>
                  <div className="text-[9px] text-gray-400">Fail-Closed</div>
                </div>
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3 text-center">
                  <div className="relative w-12 h-12 mx-auto mb-2">
                    <svg className="w-12 h-12 -rotate-90" viewBox="0 0 36 36">
                      <circle cx="18" cy="18" r="15.5" fill="none" stroke="#1f2937" strokeWidth="3" />
                      <circle cx="18" cy="18" r="15.5" fill="none" stroke={gaugeColor(readinessData.runtime_enforcement_score)}
                        strokeWidth="3" strokeDasharray={gaugeDash(readinessData.runtime_enforcement_score)} />
                    </svg>
                    <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-white">
                      {readinessData.runtime_enforcement_score.toFixed(0)}
                    </span>
                  </div>
                  <div className="text-[9px] text-gray-400">Runtime Enforcement</div>
                </div>
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3 text-center">
                  <div className="relative w-12 h-12 mx-auto mb-2">
                    <svg className="w-12 h-12 -rotate-90" viewBox="0 0 36 36">
                      <circle cx="18" cy="18" r="15.5" fill="none" stroke="#1f2937" strokeWidth="3" />
                      <circle cx="18" cy="18" r="15.5" fill="none" stroke={gaugeColor(readinessData.operational_readiness_score)}
                        strokeWidth="3" strokeDasharray={gaugeDash(readinessData.operational_readiness_score)} />
                    </svg>
                    <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-white">
                      {readinessData.operational_readiness_score.toFixed(0)}
                    </span>
                  </div>
                  <div className="text-[9px] text-gray-400">Operational</div>
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
                  "border-emerald-500/30 bg-emerald-950/10 text-emerald-300"
                }`}>
                  {readinessData.recommendation}
                </div>
              </div>
            </>
          )}
          {!readinessLoading && !readinessData && (
            <div className="text-center py-8 text-xs text-muted-foreground">Run a micro-capital audit to see deployment readiness.</div>
          )}
        </div>
      )}

      {/* ── Tab: Execution Safety ──────────────── */}
      {tab === "execution" && (
        <div className="space-y-4">
          {execLoading && <div className="text-center py-8 text-xs text-muted-foreground">Checking execution safety...</div>}
          {!execLoading && execData && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <StatCard title="Execution Safety Score" value={`${execData.score.toFixed(0)}/100`} icon={Cpu}
                  color={execData.score >= 85 ? "positive" : execData.score >= 70 ? "default" : "negative"} />
                <StatCard title="Execution Paths" value={`${execData.execution_paths?.length || 0}`} icon={GitBranch} />
                <StatCard title="All Paths Gated" value={execData.all_paths_gated ? "YES" : "NO"} icon={CheckCircle}
                  color={execData.all_paths_gated ? "positive" : "negative"} />
              </div>

              <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
                  <Cpu className="h-3.5 w-3.5 inline mr-1" />
                  Execution Path Validation
                </h2>
                <div className="space-y-3">
                  {execData.execution_paths?.map((p: any, i: number) => (
                    <div key={i} className={`rounded-lg border p-3 ${
                      p.gated ? "border-emerald-500/20 bg-emerald-950/10" : "border-red-500/20 bg-red-950/10"
                    }`}>
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          {p.gated ? (
                            <CheckCircle className="h-3.5 w-3.5 text-emerald-400" />
                          ) : (
                            <XCircle className="h-3.5 w-3.5 text-red-400" />
                          )}
                          <span className="text-xs text-white font-medium">{p.path_name}</span>
                        </div>
                        <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold ${
                          p.gated ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"
                        }`}>
                          {p.gated ? "GATED" : "UNGATED"}
                        </span>
                      </div>
                      <p className="text-[10px] text-gray-400 ml-6">{p.details}</p>
                    </div>
                  ))}
                </div>
              </div>

              {execData.risk_flags?.length > 0 && (
                <div className="rounded-xl border border-amber-500/20 bg-amber-950/10 p-4">
                  <h2 className="text-[10px] font-bold text-amber-400 uppercase tracking-widest mb-4">
                    <AlertTriangle className="h-3.5 w-3.5 inline mr-1" />
                    Risk Flags
                  </h2>
                  <div className="space-y-1">
                    {execData.risk_flags.map((flag: string, i: number) => (
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
          {!execLoading && !execData && (
            <div className="text-center py-8 text-xs text-muted-foreground">Run an audit to see execution safety data.</div>
          )}
        </div>
      )}

      {/* ── Tab: Capital Protection ───────────── */}
      {tab === "capital" && (
        <div className="space-y-4">
          {capLoading && <div className="text-center py-8 text-xs text-muted-foreground">Checking capital protection...</div>}
          {!capLoading && capData && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <StatCard title="Capital Protection Score" value={`${capData.score.toFixed(0)}/100`} icon={Lock}
                  color={capData.score >= 85 ? "positive" : capData.score >= 70 ? "default" : "negative"} />
                <StatCard title="Limits Checked" value={`${capData.limit_checks?.length || 0}`} icon={BarChart3} />
                <StatCard title="Kill Switch Triggers" value={capData.kill_switch_triggers ? "YES" : "NO"} icon={Radio}
                  color={capData.kill_switch_triggers ? "positive" : "negative"} />
              </div>

              <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
                  <Lock className="h-3.5 w-3.5 inline mr-1" />
                  Position &amp; Exposure Limits
                </h2>
                <div className="space-y-3">
                  {capData.limit_checks?.map((c: any, i: number) => (
                    <div key={i} className={`rounded-lg border p-3 ${
                      !c.can_exceed ? "border-emerald-500/20 bg-emerald-950/10" : "border-red-500/20 bg-red-950/10"
                    }`}>
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          {!c.can_exceed ? (
                            <CheckCircle className="h-3.5 w-3.5 text-emerald-400" />
                          ) : (
                            <XCircle className="h-3.5 w-3.5 text-red-400" />
                          )}
                          <span className="text-xs text-white font-medium">{c.limit_name}</span>
                        </div>
                        <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold ${
                          !c.can_exceed ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"
                        }`}>
                          {c.can_exceed ? "CAN EXCEED" : "ENFORCED"}
                        </span>
                      </div>
                      <p className="text-[10px] text-gray-400 ml-6">{c.details}</p>
                    </div>
                  ))}
                </div>
              </div>

              {capData.risk_flags?.length > 0 && (
                <div className="rounded-xl border border-amber-500/20 bg-amber-950/10 p-4">
                  <h2 className="text-[10px] font-bold text-amber-400 uppercase tracking-widest mb-4">
                    <AlertTriangle className="h-3.5 w-3.5 inline mr-1" />
                    Risk Flags
                  </h2>
                  <div className="space-y-1">
                    {capData.risk_flags.map((flag: string, i: number) => (
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
          {!capLoading && !capData && (
            <div className="text-center py-8 text-xs text-muted-foreground">Run an audit to see capital protection data.</div>
          )}
        </div>
      )}

      {/* ── Tab: Fail-Closed ──────────────────── */}
      {tab === "failclosed" && (
        <div className="space-y-4">
          {fcLoading && <div className="text-center py-8 text-xs text-muted-foreground">Simulating failure scenarios...</div>}
          {!fcLoading && fcData && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <StatCard title="Fail-Closed Score" value={`${fcData.score.toFixed(0)}/100`} icon={Shield}
                  color={fcData.score >= 85 ? "positive" : fcData.score >= 70 ? "default" : "negative"} />
                <StatCard title="Scenarios" value={`${fcData.scenarios?.length || 0}`} icon={Activity} />
                <StatCard title="All Blocked" value={fcData.all_blocked ? "YES" : "NO"} icon={CheckCircle}
                  color={fcData.all_blocked ? "positive" : "negative"} />
              </div>

              <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
                  <Wifi className="h-3.5 w-3.5 inline mr-1" />
                  Fail-Closed Scenario Matrix
                </h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-gray-800 text-[10px] text-gray-500 uppercase tracking-wider">
                        <th className="text-left py-2 pr-2">Scenario</th>
                        <th className="text-center py-2 pr-2">Blocks Execution</th>
                        <th className="text-left py-2 pr-2">Details</th>
                      </tr>
                    </thead>
                    <tbody>
                      {fcData.scenarios?.map((s: any, i: number) => (
                        <tr key={i} className="border-b border-gray-900">
                          <td className="py-2 pr-2 text-gray-300 font-medium">{s.scenario}</td>
                          <td className="py-2 pr-2 text-center">
                            {s.blocks_execution ? (
                              <span className="text-emerald-400 text-[10px] font-bold">BLOCKED</span>
                            ) : (
                              <span className="text-red-400 text-[10px] font-bold">NOT BLOCKED</span>
                            )}
                          </td>
                          <td className="py-2 pr-2 text-[10px] text-gray-400">{s.details}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {fcData.risk_flags?.length > 0 && (
                <div className="rounded-xl border border-amber-500/20 bg-amber-950/10 p-4">
                  <h2 className="text-[10px] font-bold text-amber-400 uppercase tracking-widest mb-4">
                    <AlertTriangle className="h-3.5 w-3.5 inline mr-1" />
                    Risk Flags
                  </h2>
                  <div className="space-y-1">
                    {fcData.risk_flags.map((flag: string, i: number) => (
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
          {!fcLoading && !fcData && (
            <div className="text-center py-8 text-xs text-muted-foreground">Run an audit to see fail-closed test results.</div>
          )}
        </div>
      )}

      {/* ── Tab: Runtime Enforcement ──────────── */}
      {tab === "runtime" && (
        <div className="space-y-4">
          {rtLoading && <div className="text-center py-8 text-xs text-muted-foreground">Checking runtime enforcement...</div>}
          {!rtLoading && rtData && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <StatCard title="Runtime Enforcement" value={`${rtData.score.toFixed(0)}/100`} icon={Sliders}
                  color={rtData.score >= 85 ? "positive" : rtData.score >= 70 ? "default" : "negative"} />
                <StatCard title="Checks" value={`${rtData.checks?.length || 0}`} icon={GitBranch} />
                <StatCard title="All Blocked" value={rtData.all_blocked ? "YES" : "NO"} icon={CheckCircle}
                  color={rtData.all_blocked ? "positive" : "negative"} />
              </div>

              <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
                  <Sliders className="h-3.5 w-3.5 inline mr-1" />
                  Blocked Trade Simulations
                </h2>
                <div className="space-y-3">
                  {rtData.checks?.map((c: any, i: number) => (
                    <div key={i} className={`rounded-lg border p-3 ${
                      c.blocked ? "border-emerald-500/20 bg-emerald-950/10" : "border-red-500/20 bg-red-950/10"
                    }`}>
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          {c.blocked ? (
                            <CheckCircle className="h-3.5 w-3.5 text-emerald-400" />
                          ) : (
                            <XCircle className="h-3.5 w-3.5 text-red-400" />
                          )}
                          <span className="text-xs text-white font-medium">Can trade? — {c.check_name}</span>
                        </div>
                        <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold ${
                          c.blocked ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"
                        }`}>
                          {c.blocked ? "BLOCKED" : "NOT BLOCKED"}
                        </span>
                      </div>
                      <p className="text-[10px] text-gray-400 ml-6">{c.details}</p>
                    </div>
                  ))}
                </div>
              </div>

              {rtData.risk_flags?.length > 0 && (
                <div className="rounded-xl border border-amber-500/20 bg-amber-950/10 p-4">
                  <h2 className="text-[10px] font-bold text-amber-400 uppercase tracking-widest mb-4">
                    <AlertTriangle className="h-3.5 w-3.5 inline mr-1" />
                    Risk Flags
                  </h2>
                  <div className="space-y-1">
                    {rtData.risk_flags.map((flag: string, i: number) => (
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
          {!rtLoading && !rtData && (
            <div className="text-center py-8 text-xs text-muted-foreground">Run an audit to see runtime enforcement data.</div>
          )}
        </div>
      )}

      {/* ── Tab: Operational Readiness ────────── */}
      {tab === "operational" && (
        <div className="space-y-4">
          {opLoading && <div className="text-center py-8 text-xs text-muted-foreground">Checking operational readiness...</div>}
          {!opLoading && opData && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                <StatCard title="Overall Readiness" value={`${opData.overall_score.toFixed(0)}/100`} icon={ClipboardList}
                  color={opData.overall_score >= 85 ? "positive" : opData.overall_score >= 70 ? "default" : "negative"} />
                <StatCard title="Logging" value={`${opData.logging_score.toFixed(0)}/100`} icon={Eye}
                  color={opData.logging_score >= 85 ? "positive" : opData.logging_score >= 70 ? "default" : "negative"} />
                <StatCard title="Monitoring" value={`${opData.monitoring_score.toFixed(0)}/100`} icon={BarChart3}
                  color={opData.monitoring_score >= 85 ? "positive" : opData.monitoring_score >= 70 ? "default" : "negative"} />
                <StatCard title="Kill Switch Visibility" value={`${opData.kill_switch_visibility_score.toFixed(0)}/100`} icon={Radio}
                  color={opData.kill_switch_visibility_score >= 85 ? "positive" : opData.kill_switch_visibility_score >= 70 ? "default" : "negative"} />
              </div>

              {opData.details?.logging && (
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                  <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
                    <Eye className="h-3.5 w-3.5 inline mr-1" />
                    Logging Checklist
                  </h2>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                    {Object.entries(opData.details.logging).map(([k, v]: [string, any]) => (
                      <div key={k} className="flex items-center gap-2 text-[10px]">
                        {v ? (
                          <CheckCircle className="h-3 w-3 text-emerald-400" />
                        ) : (
                          <XCircle className="h-3 w-3 text-red-400" />
                        )}
                        <span className="text-gray-300">{k.replace(/_/g, " ")}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {opData.details?.monitoring && (
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                  <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
                    <BarChart3 className="h-3.5 w-3.5 inline mr-1" />
                    Monitoring Checklist
                  </h2>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                    {Object.entries(opData.details.monitoring).map(([k, v]: [string, any]) => (
                      <div key={k} className="flex items-center gap-2 text-[10px]">
                        {v ? (
                          <CheckCircle className="h-3 w-3 text-emerald-400" />
                        ) : (
                          <XCircle className="h-3 w-3 text-red-400" />
                        )}
                        <span className="text-gray-300">{k.replace(/_/g, " ")}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {opData.details?.kill_switch_visibility && (
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                  <h2 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
                    <Radio className="h-3.5 w-3.5 inline mr-1" />
                    Kill Switch Visibility
                  </h2>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                    {Object.entries(opData.details.kill_switch_visibility).map(([k, v]: [string, any]) => (
                      <div key={k} className="flex items-center gap-2 text-[10px]">
                        {v ? (
                          <CheckCircle className="h-3 w-3 text-emerald-400" />
                        ) : (
                          <XCircle className="h-3 w-3 text-red-400" />
                        )}
                        <span className="text-gray-300">{k.replace(/_/g, " ")}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {opData.risk_flags?.length > 0 && (
                <div className="rounded-xl border border-amber-500/20 bg-amber-950/10 p-4">
                  <h2 className="text-[10px] font-bold text-amber-400 uppercase tracking-widest mb-4">
                    <AlertTriangle className="h-3.5 w-3.5 inline mr-1" />
                    Risk Flags
                  </h2>
                  <div className="space-y-1">
                    {opData.risk_flags.map((flag: string, i: number) => (
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
          {!opLoading && !opData && (
            <div className="text-center py-8 text-xs text-muted-foreground">Run an audit to see operational readiness data.</div>
          )}
        </div>
      )}
    </div>
  );
}
