const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}/api/v1${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

async function fetchRaw<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export interface Market {
  id: string;
  condition_id: string;
  slug: string | null;
  title: string | null;
  volume: number | null;
  liquidity: number | null;
  resolved: boolean;
  created_at: string | null;
}

export interface Wallet {
  address: string;
  total_trades: number;
  total_volume: number;
  realized_pnl: number;
  win_rate: number | null;
  current_rank: number | null;
  tags: string[] | null;
}

export interface Signal {
  id: string;
  market_id: string | null;
  signal_type: string;
  direction: string;
  confidence: number;
  reasoning: string | null;
  source_agent: string | null;
  is_active: boolean;
  generated_at: string | null;
}

export interface Trade {
  id: string;
  market_id: string | null;
  trade_type: string;
  status: string;
  side: string;
  outcome: string;
  size: number;
  price: number | null;
  pnl: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  created_at: string | null;
}

// ── Cockpit types ──────────────────────────────────

export interface CurrentMode {
  mode: string;
  reason: string;
  is_manual_override: boolean;
  operator: string;
  updated_at: number;
  ttl_seconds: number | null;
  color: string;
  sensitivity: number;
}

export interface TransitionRecord {
  id: string;
  from_mode: string;
  to_mode: string;
  reason: string;
  is_manual: boolean;
  operator: string;
  duration_seconds: number | null;
  created_at: string | null;
}

export interface StabilityMetrics {
  flip_count: number;
  escalation_chain_depth: number;
  hysteresis_rejected_count: number;
  time_in_mode_pct: Record<string, number>;
  total_transitions_24h: number;
}

export interface CockpitOverview {
  current_mode: CurrentMode;
  recent_transitions: TransitionRecord[];
  stability_metrics: StabilityMetrics;
  pipeline: Record<string, any>;
  recorded_snapshots_count: number;
}

export interface InstabilityIndicators {
  flip_count: number;
  flip_rate_per_min: number;
  chain_depth: number;
  hysteresis_rejected: number;
  oscillation_detected: boolean;
  oscillation_events: number;
}

export interface CockpitInstability {
  instability_score: number;
  state: "stable" | "watch" | "unstable";
  status_message: string;
  primary_drivers: string[];
  indicators: InstabilityIndicators;
  current_mode: string;
  has_override: boolean;
  trend: string;
}

export interface CockpitExplanation {
  current_mode: string;
  is_manual_override: boolean;
  primary_driver: string;
  contributing_factors: { factor: string; classification: string; impact: string }[];
  transition_summary: string;
  last_transition: {
    from_mode: string | null;
    to_mode: string | null;
    reason: string | null;
    created_at: string | null;
    is_manual: boolean;
  } | null;
  mode_color: string;
}

export interface ModeSnapshotRecord {
  mode_before: string;
  mode_proposed: string;
  mode_after: string;
  reason: string;
  sensitivity: number;
  raw_db: number;
  raw_redis: number;
  raw_pending: number;
}

export interface SimulationSummary {
  total_steps: number;
  transitions: number;
  total_duration_s: number;
  flip_count: number;
  max_escalation_chain: number;
  time_in_mode_pct: Record<string, number>;
  oscillation_events: number;
  mode_proposed_but_rejected: number;
  rejected_by_hysteresis: number;
  rejected_by_hold: number;
}

export interface ModeDebugStatus {
  mode: string;
  reason: string;
  has_override: boolean;
  operator: string;
  ttl_seconds: number | null;
}

// ── System / Control types ──────────────────────────

export interface RedisStatus {
  used_memory_mb: number;
  peak_memory_mb: number;
  maxmemory_mb: number;
  utilization_percent: number;
  key_count: number;
  keys_with_expiry: number;
  avg_ttl_seconds: number;
}

export interface SystemMode {
  mode: string;
  reason: string;
  is_manual_override: boolean;
  operator: string;
  updated_at: string;
  ttl_seconds: number | null;
}

export interface KillSwitchResponse {
  kill_switch: boolean;
  message: string;
}

export interface SimulationResult {
  id: string;
  strategy: string;
  status: string;
  metrics: {
    total_pnl: number;
    win_rate: number;
    sharpe_ratio: number;
    max_drawdown: number;
    total_trades: number;
  };
  trades: any[];
}

export const api = {
  // Markets
  markets: {
    list: (params?: { skip?: number; limit?: number }) =>
      fetchAPI<Market[]>(`/markets?${new URLSearchParams(params as any)}`),
    get: (id: string) => fetchAPI<Market>(`/markets/${id}`),
    getBySlug: (slug: string) => fetchAPI<Market>(`/markets/slug/${slug}`),
  },

  // Wallets
  wallets: {
    list: (params?: { skip?: number; limit?: number; sort_by?: string }) =>
      fetchAPI<Wallet[]>(`/wallets?${new URLSearchParams(params as any)}`),
    get: (address: string) => fetchAPI<Wallet>(`/wallets/${address}`),
    leaderboard: (limit?: number) =>
      fetchAPI<Wallet[]>(`/wallets/leaderboard/top?limit=${limit || 20}`),
  },

  // Signals
  signals: {
    list: (params?: {
      skip?: number;
      limit?: number;
      is_active?: boolean;
      min_confidence?: number;
    }) => fetchAPI<Signal[]>(`/signals?${new URLSearchParams(params as any)}`),
    get: (id: string) => fetchAPI<Signal>(`/signals/${id}`),
  },

  // Trades
  trades: {
    list: (params?: { skip?: number; limit?: number; status?: string }) =>
      fetchAPI<Trade[]>(`/trades?${new URLSearchParams(params as any)}`),
    get: (id: string) => fetchAPI<Trade>(`/trades/${id}`),
  },

  // Cockpit
  cockpit: {
    overview: () => fetchAPI<CockpitOverview>("/cockpit/overview"),
    instability: (windowMinutes = 30) =>
      fetchAPI<CockpitInstability>(`/cockpit/instability?window_minutes=${windowMinutes}`),
    explanation: () => fetchAPI<CockpitExplanation>("/cockpit/explanation"),
  },

  // Raw debug endpoints (not under /api/v1, use direct fetch)
  debug: {
    recordedSnapshots: (limit = 100) =>
      fetchRaw<ModeSnapshotRecord[]>(`${API_BASE}/debug/mode/recorded-snapshots?limit=${limit}`),
    simulate: (cycles = 3, seed?: number) =>
      fetchRaw<SimulationSummary>(`${API_BASE}/debug/mode/simulate?cycles=${cycles}${seed !== undefined ? `&seed=${seed}` : ""}`),
    modeStatus: () => fetchRaw<ModeDebugStatus>(`${API_BASE}/debug/mode/status`),
  },

  // Health
  health: {
    ping: () => fetchAPI<{ ping: string }>("/health/ping"),
    status: () => fetchAPI<{
      status: string;
      timestamp: string;
      metrics: {
        portfolio_value: number;
        drawdown: number;
        kill_switch_active: boolean;
        circuit_breaker_active: boolean;
        active_strategies: number;
        ws_events_last_minute: number;
      };
      alerts: string[];
    }>("/health/status"),
  },

  // Portfolio
  portfolio: {
    summary: () => fetchAPI<any>("/portfolio/summary"),
    history: (hours = 168) => fetchAPI<any[]>(`/portfolio/history?hours=${hours}`),
    positions: (status?: string) =>
      fetchAPI<any[]>(`/portfolio/positions${status ? `?status=${status}` : ""}`),
    strategies: () => fetchAPI<any[]>("/portfolio/strategies"),
    strategyDetail: (agentId: string) => fetchAPI<any>(`/portfolio/strategies/${agentId}`),
    strategyPnlCurve: (agentId: string) => fetchAPI<any[]>(`/portfolio/strategies/${agentId}/pnl-curve`),
    tradeTimeline: (tradeId: string) => fetchAPI<any>(`/portfolio/trades/${tradeId}/timeline`),
    exposure: () => fetchAPI<any>("/portfolio/exposure"),
  },

  // Monitoring
  monitoring: {
    tradeMetrics: (tradeId: string) => fetchAPI<any>(`/monitoring/trades/${tradeId}`),
    orderMetrics: (orderId: string) => fetchAPI<any>(`/monitoring/orders/${orderId}`),
    positionMetrics: (marketId: string) => fetchAPI<any>(`/monitoring/positions/${marketId}`),
    portfolioMetrics: () => fetchAPI<any>("/monitoring/portfolio"),
    strategyMetrics: (agentId: string) => fetchAPI<any>(`/monitoring/strategy/${agentId}`),
  },

  // Analytics
  analytics: {
    strategySummary: (days = 7) => fetchAPI<any>(`/analytics/strategy-summary?days=${days}`),
    slippageSummary: (days = 7) => fetchAPI<any>(`/analytics/slippage-summary?days=${days}`),
  },

  // System mode
  system: {
    mode: () => fetchAPI<SystemMode>("/system/mode"),
    redis: () => fetchAPI<RedisStatus>("/system/redis"),
  },

  // Execution control
  execution: {
    killSwitch: () =>
      fetchAPI<KillSwitchResponse>("/execution/safety/kill-switch", { method: "POST" }),
    emergencyStop: () =>
      fetchAPI<{ status: string; closed_count: number }>("/execution/emergency/close-all", { method: "POST" }),
  },

  // Backtesting / simulation
  backtesting: {
    simulate: (strategy: string) =>
      fetchAPI<SimulationResult>(`/backtesting/strategies/${strategy}/simulate`, { method: "POST" }),
  },

  // Strategy names (for simulation dropdown)
  strategies: {
    names: () => fetchAPI<{ strategies: string[] }>("/strategies/names"),
  },

  // ── Shadow Trading ─────────────────────────────
  shadow: {
    executions: (params?: { status?: string; strategy?: string; market_id?: string }) => {
      const search = new URLSearchParams();
      if (params?.status) search.set("status", params.status);
      if (params?.strategy) search.set("strategy", params.strategy);
      if (params?.market_id) search.set("market_id", params.market_id);
      return fetchAPI<any>(`/shadow/executions?${search}`);
    },
    getExecution: (id: string) => fetchAPI<any>(`/shadow/executions/${id}`),
    sync: () => fetchAPI<{ created: number; skipped: number; total_signals: number }>("/shadow/sync", { method: "POST" }),
    refreshPrices: () => fetchAPI<{ updated: number; closed: number }>("/shadow/refresh-prices", { method: "POST" }),
    strategies: () => fetchAPI<{ strategies: any[] }>("/shadow/strategies"),
    performance: () => fetchAPI<any>("/shadow/performance"),
    analytics: (params?: { start?: string; end?: string }) => {
      const search = new URLSearchParams();
      if (params?.start) search.set("start", params.start);
      if (params?.end) search.set("end", params.end);
      return fetchAPI<{ analytics: any[] }>(`/shadow/analytics?${search}`);
    },
    strategyAnalytics: (strategy: string, params?: { start?: string; end?: string }) => {
      const search = new URLSearchParams();
      if (params?.start) search.set("start", params.start);
      if (params?.end) search.set("end", params.end);
      return fetchAPI<any>(`/shadow/analytics/${strategy}?${search}`);
    },
    benchmarks: () => fetchAPI<{ benchmarks: any[] }>("/shadow/benchmarks"),
    promotions: () => fetchAPI<{ promotions: any[] }>("/shadow/promotion"),
    strategyPromotion: (strategy: string) => fetchAPI<any>(`/shadow/promotion/${strategy}`),
  },

  // ── Research ─────────────────────────────────
  research: {
    registry: (status?: string) =>
      fetchAPI<{ strategies: any[] }>(`/research/registry${status ? `?status=${status}` : ""}`),
    registryEntry: (strategyId: string) =>
      fetchAPI<{ strategy: any }>(`/research/registry/${strategyId}`),
    registryHistory: (strategyId: string) =>
      fetchAPI<{ history: any[] }>(`/research/registry/${strategyId}/history`),
    promote: (strategyId: string, targetStatus: string, notes = "") =>
      fetchAPI<{ status: string; strategy: any }>(
        `/research/registry/${strategyId}/promote?target_status=${targetStatus}&notes=${notes}`,
        { method: "POST" },
      ),
    retire: (strategyId: string, successor?: string, notes = "") => {
      let q = `/research/registry/${strategyId}/retire?notes=${notes}`;
      if (successor) q += `&successor=${successor}`;
      return fetchAPI<{ status: string; strategy: any }>(q, { method: "POST" });
    },
    champion: () => fetchAPI<any>("/research/champion"),
    health: () => fetchAPI<{ health: any[] }>("/research/health"),
    strategyHealth: (strategy: string) => fetchAPI<any>(`/research/health/${strategy}`),
    invalidateHealth: () =>
      fetchAPI<{ status: string }>("/research/health/invalidate", { method: "POST" }),
    report: (strategy: string) => fetchAPI<any>(`/research/report/${strategy}`),
    portfolioReport: () => fetchAPI<any>("/research/report/portfolio"),
    invalidateReport: () =>
      fetchAPI<{ status: string }>("/research/report/invalidate", { method: "POST" }),
  },

  // ── Tournament ────────────────────────────────
  tournament: {
    rankings: () => fetchAPI<{ rankings: any[] }>("/tournament/rankings"),
    allocations: (mode = "equal", capital = 100000) =>
      fetchAPI<any>(`/tournament/allocations?mode=${mode}&capital=${capital}`),
    allAllocations: (capital = 100000) =>
      fetchAPI<{ modes: any[] }>(`/tournament/allocations/all?capital=${capital}`),
    simulator: (capital = 100000, mode = "equal") =>
      fetchAPI<any>(`/tournament/simulator?capital=${capital}&mode=${mode}`),
    promotions: () => fetchAPI<{ recommendations: any[] }>("/tournament/promotions"),
  },

  // ── Research Agents ────────────────────────────
  researchAgents: {
    signals: (lifecycle?: string) =>
      fetchAPI<{ signals: any[] }>(`/research-agents/signals${lifecycle ? `?lifecycle=${lifecycle}` : ""}`),
    consensus: () => fetchAPI<{ approved_count: number; rejected_count: number; pending_count: number; approved: any[]; rejected: any[]; pending: any[] }>("/research-agents/consensus"),
    health: () => fetchAPI<{ agents: any[] }>("/research-agents/health"),
    registry: () => fetchAPI<{ stats: any; agent_counts: any[] }>("/research-agents/registry"),
    run: () => fetchAPI<any>("/research-agents/run", { method: "POST" }),
    status: () => fetchAPI<any>("/research-agents/status"),
  },
};
