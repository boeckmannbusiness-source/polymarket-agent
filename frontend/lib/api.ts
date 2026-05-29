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
  health: () => fetchAPI<{ status: string }>("/health"),
};
