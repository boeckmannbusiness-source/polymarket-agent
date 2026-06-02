"use client";

import { useMarketExposure } from "@/lib/hooks";
import { ExposurePanel } from "@/components/ExposurePanel";
import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";

export default function ExposurePage() {
  const router = useRouter();
  const { data: exposure, loading } = useMarketExposure();

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <button
          onClick={() => router.push("/portfolio")}
          className="text-gray-500 hover:text-white transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <h1 className="text-xl font-bold text-white">Market Exposure</h1>
      </div>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-6">
        {loading && !exposure ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-20 animate-pulse rounded-lg bg-gray-800/50" />
              ))}
            </div>
          </div>
        ) : exposure ? (
          <ExposurePanel
            totalLong={exposure.total_long_exposure}
            totalShort={exposure.total_short_exposure}
            netExposure={exposure.net_exposure}
            concentrationRisk={exposure.concentration_risk_pct}
            largestPositions={exposure.largest_positions || []}
            exposureByMarket={exposure.exposure_by_market || []}
          />
        ) : (
          <div className="text-center py-16 text-gray-500">
            <p className="text-sm">No exposure data available</p>
          </div>
        )}
      </div>
    </div>
  );
}
