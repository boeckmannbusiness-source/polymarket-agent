"use client";

interface RiskGaugeProps {
  score: number;
  label?: string;
  size?: "sm" | "md" | "lg";
}

export function RiskGauge({ score, label, size = "md" }: RiskGaugeProps) {
  const clamped = Math.max(0, Math.min(100, score));
  const dim = size === "sm" ? 80 : size === "lg" ? 160 : 120;
  const strokeWidth = size === "sm" ? 6 : size === "lg" ? 12 : 8;
  const radius = (dim - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (clamped / 100) * circumference;

  const color = clamped >= 80 ? "stroke-emerald-500" : clamped >= 50 ? "stroke-amber-500" : "stroke-red-500";

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={dim} height={dim} className="transform -rotate-90">
        <circle cx={dim / 2} cy={dim / 2} r={radius} fill="none" stroke="currentColor" strokeWidth={strokeWidth} className="text-gray-800" />
        <circle
          cx={dim / 2}
          cy={dim / 2}
          r={radius}
          fill="none"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          className={color}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 0.5s ease" }}
        />
      </svg>
      <span className={`font-bold font-mono ${size === "sm" ? "text-lg" : size === "lg" ? "text-3xl" : "text-2xl"} ${color.replace("stroke-", "text-")}`}>
        {clamped.toFixed(0)}
      </span>
      {label && <span className="text-[10px] text-muted-foreground uppercase tracking-wider">{label}</span>}
    </div>
  );
}
