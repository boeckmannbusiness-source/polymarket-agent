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

  // Health
  health: () => fetchAPI<{ status: string }>("/health"),
};
