"use client";

interface CircuitBreakerBadgeProps {
  name: string;
  triggered: boolean;
  reason?: string;
  onClick?: () => void;
}

export function CircuitBreakerBadge({ name, triggered, reason, onClick }: CircuitBreakerBadgeProps) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs transition-colors ${
        triggered
          ? "border-red-700 bg-red-950/50 text-red-400 hover:bg-red-950"
          : "border-border bg-card text-muted-foreground hover:bg-accent"
      }`}
    >
      <span className={`w-2 h-2 rounded-full ${triggered ? "bg-red-500 animate-pulse" : "bg-emerald-500"}`} />
      <span className="font-mono uppercase text-[10px]">{name.replace(/_/g, " ")}</span>
      {triggered && <span className="text-[10px] text-red-300 truncate max-w-[120px]">{reason || "active"}</span>}
    </button>
  );
}
