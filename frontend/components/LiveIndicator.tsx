"use client";

type LiveStatus = "connecting" | "connected" | "disconnected" | "reconnecting";

interface LiveIndicatorProps {
  status: LiveStatus;
  label?: string;
}

const statusConfig: Record<LiveStatus, { color: string; pulse: string }> = {
  connected: { color: "bg-emerald-500", pulse: "animate-pulse" },
  connecting: { color: "bg-amber-500", pulse: "animate-pulse" },
  reconnecting: { color: "bg-amber-500", pulse: "animate-pulse" },
  disconnected: { color: "bg-red-500", pulse: "" },
};

export function LiveIndicator({ status, label }: LiveIndicatorProps) {
  const cfg = statusConfig[status];
  return (
    <div className="flex items-center gap-2 text-xs font-mono">
      <span className={`inline-block w-2 h-2 rounded-full ${cfg.color} ${cfg.pulse}`} />
      <span className="text-muted-foreground">{label ?? status}</span>
    </div>
  );
}
