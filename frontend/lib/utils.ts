import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatPnl(pnl: number | null): string {
  if (pnl === null) return "-";
  const prefix = pnl >= 0 ? "+" : "";
  return `${prefix}$${pnl.toFixed(2)}`;
}

export function formatPercent(value: number | null): string {
  if (value === null) return "-";
  return `${(value * 100).toFixed(1)}%`;
}

export function formatAddress(address: string, chars = 6): string {
  return `${address.slice(0, chars)}...${address.slice(-4)}`;
}

export function formatNumber(value: number | null): string {
  if (value === null) return "-";
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toFixed(2);
}

export function confidenceColor(confidence: number): string {
  if (confidence >= 0.8) return "text-green-400";
  if (confidence >= 0.6) return "text-yellow-400";
  return "text-red-400";
}

export function confidenceBg(confidence: number): string {
  if (confidence >= 0.8) return "bg-green-500";
  if (confidence >= 0.6) return "bg-yellow-500";
  return "bg-red-500";
}

export function timeAgo(dateStr: string | null): string {
  if (!dateStr) return "-";
  const date = new Date(dateStr);
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

// ── Mode colors ─────────────────────────────────────

export const MODE_COLORS: Record<string, string> = {
  normal: "#00C853",
  degraded: "#FFD600",
  protected: "#FF9800",
  read_only: "#9C27B0",
  emergency_stop: "#FF1744",
};

export const MODE_COLORS_CSS: Record<string, string> = {
  normal: "text-green-400",
  degraded: "text-yellow-400",
  protected: "text-orange-400",
  read_only: "text-purple-400",
  emergency_stop: "text-red-400",
};

export const MODE_BG_CSS: Record<string, string> = {
  normal: "bg-green-500/20 border-green-500/30",
  degraded: "bg-yellow-500/20 border-yellow-500/30",
  protected: "bg-orange-500/20 border-orange-500/30",
  read_only: "bg-purple-500/20 border-purple-500/30",
  emergency_stop: "bg-red-500/20 border-red-500/30",
};

export const MODE_INDICES: Record<string, number> = {
  normal: 0,
  degraded: 1,
  protected: 2,
  read_only: 3,
  emergency_stop: 4,
};