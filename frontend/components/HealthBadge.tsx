import { cn } from "@/lib/utils";
import { ShieldCheck, ShieldAlert, ShieldOff } from "lucide-react";

interface HealthBadgeProps {
  status: string;
  size?: "sm" | "md";
}

const healthConfig: Record<string, { color: string; bg: string; icon: any; label: string }> = {
  healthy: {
    color: "text-emerald-500",
    bg: "bg-emerald-500/10 border-emerald-500/30",
    icon: ShieldCheck,
    label: "Healthy",
  },
  degraded: {
    color: "text-yellow-500",
    bg: "bg-yellow-500/10 border-yellow-500/30",
    icon: ShieldAlert,
    label: "Degraded",
  },
  critical: {
    color: "text-rose-500",
    bg: "bg-rose-500/10 border-rose-500/30",
    icon: ShieldOff,
    label: "Critical",
  },
};

export function HealthBadge({ status, size = "md" }: HealthBadgeProps) {
  const config = healthConfig[status] || healthConfig.degraded;
  const Icon = config.icon;

  return (
    <div className={cn(
      "inline-flex items-center gap-1.5 rounded-md border px-2 py-1",
      config.bg,
      size === "sm" ? "text-[10px]" : "text-xs",
    )}>
      <Icon className={cn("h-3 w-3", config.color)} />
      <span className={cn("font-bold uppercase tracking-wider", config.color)}>
        {config.label}
      </span>
    </div>
  );
}
