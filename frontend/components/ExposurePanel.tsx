"use client";

import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown, AlertTriangle } from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from "recharts";

interface ExposureSummary {
  market_id: string;
  market_slug?: string | null;
  market_title?: string | null;
  direction: string;
  size: number;
  current_price?: number | null;
  exposure_value: number;
  pct_of_portfolio: number;
  unrealized_pnl: number;
}

interface ExposurePanelProps {
  totalLong: number;
  totalShort: number;
  netExposure: number;
  concentrationRisk: number;
  largestPositions: ExposureSummary[];
  exposureByMarket: ExposureSummary[];
  loading?: boolean;
}

export function ExposurePanel({
  totalLong, totalShort, netExposure, concentrationRisk,
  largestPositions, exposureByMarket, loading,
}: ExposurePanelProps) {
  if (loading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-8 animate-pulse rounded bg-gray-800/50" />
        ))}
      </div>
    );
  }

  const barData = exposureByMarket.slice(0, 8).map((e) => ({
    name: e.market_slug || e.market_id.slice(0, 8),
    exposure: e.exposure_value,
    pnl: e.unrealized_pnl,
  }));

  return (
    <div className="space-y-4">
      {/* Summary metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-3">
          <div className="flex items-center gap-1 text-[10px] text-gray-500 uppercase tracking-wider">
            <TrendingUp className="h-3 w-3 text-emerald-500" />
            Long
          </div>
          <div className="text-sm font-bold font-mono text-emerald-500 mt-1">${totalLong.toFixed(2)}</div>
        </div>
        <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-3">
          <div className="flex items-center gap-1 text-[10px] text-gray-500 uppercase tracking-wider">
            <TrendingDown className="h-3 w-3 text-rose-500" />
            Short
          </div>
          <div className="text-sm font-bold font-mono text-rose-500 mt-1">${totalShort.toFixed(2)}</div>
        </div>
        <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-3">
          <div className="flex items-center gap-1 text-[10px] text-gray-500 uppercase tracking-wider">
            Net
          </div>
          <div className={cn(
            "text-sm font-bold font-mono mt-1",
            netExposure >= 0 ? "text-emerald-500" : "text-rose-500",
          )}>
            ${netExposure.toFixed(2)}
          </div>
        </div>
        <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-3">
          <div className="flex items-center gap-1 text-[10px] text-gray-500 uppercase tracking-wider">
            <AlertTriangle className={cn("h-3 w-3", concentrationRisk > 30 ? "text-rose-500" : "text-gray-500")} />
            Concentration
          </div>
          <div className={cn(
            "text-sm font-bold font-mono mt-1",
            concentrationRisk > 30 ? "text-rose-500" : concentrationRisk > 15 ? "text-yellow-500" : "text-gray-300",
          )}>
            {concentrationRisk.toFixed(1)}%
          </div>
        </div>
      </div>

      {/* Largest positions */}
      <div>
        <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Largest Positions</div>
        <div className="space-y-1">
          {largestPositions.slice(0, 5).map((pos, i) => (
            <div key={i} className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-gray-900/50">
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-xs text-white truncate max-w-[150px]">
                  {pos.market_slug || pos.market_id.slice(0, 8)}
                </span>
                <span className={cn(
                  "text-[10px] font-bold rounded px-1",
                  pos.direction === "BUY" ? "bg-emerald-900/40 text-emerald-400" : "bg-rose-900/40 text-rose-400",
                )}>
                  {pos.direction}
                </span>
              </div>
              <div className="flex items-center gap-4 text-xs font-mono">
                <span className="text-gray-400">${pos.exposure_value.toFixed(2)}</span>
                <span className={pos.unrealized_pnl >= 0 ? "text-emerald-500" : "text-rose-500"}>
                  {pos.unrealized_pnl >= 0 ? "+" : ""}{pos.unrealized_pnl.toFixed(2)}
                </span>
                <span className="text-gray-600 w-10 text-right">{pos.pct_of_portfolio.toFixed(1)}%</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Exposure bar chart */}
      {barData.length > 0 && (
        <div className="h-[120px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={barData} layout="vertical" margin={{ left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" horizontal={false} />
              <XAxis type="number" hide />
              <YAxis dataKey="name" type="category" stroke="#666" fontSize={9} axisLine={false} tickLine={false} width={60} />
              <Tooltip
                contentStyle={{ backgroundColor: "#000", border: "1px solid #222", borderRadius: "8px", fontSize: "11px" }}
                formatter={(value: number) => [`$${value.toFixed(2)}`, "Exposure"]}
              />
              <Bar dataKey="exposure" radius={[0, 3, 3, 0]}>
                {barData.map((_, idx) => (
                  <Cell key={idx} fill={_.pnl >= 0 ? "#10b981" : "#f43f5e"} fillOpacity={0.7} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
