import { cn } from "@/lib/utils";
import { LucideIcon } from "lucide-react";

interface StatCardProps {
  title: string;
  value: string;
  change?: string;
  icon?: LucideIcon;
  color?: "default" | "positive" | "negative" | "warning";
  subtitle?: string;
  loading?: boolean;
}

const colorMap = {
  default: "text-gray-300",
  positive: "text-emerald-500",
  negative: "text-rose-500",
  warning: "text-yellow-500",
};

export function StatCard({ title, value, change, icon: Icon, color = "default", subtitle, loading }: StatCardProps) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-widest">{title}</span>
        {Icon && <Icon className="h-3.5 w-3.5 text-gray-500" />}
      </div>
      {loading ? (
        <div className="h-7 w-24 animate-pulse rounded bg-gray-800" />
      ) : (
        <div className={cn("text-xl font-bold font-mono tracking-tight", colorMap[color])}>{value}</div>
      )}
      {subtitle && <div className="text-[10px] text-gray-600 mt-0.5">{subtitle}</div>}
      {change && (
        <div className={cn("text-[11px] font-medium mt-1", color === "positive" ? "text-emerald-500" : "text-rose-500")}>
          {change}
        </div>
      )}
    </div>
  );
}
