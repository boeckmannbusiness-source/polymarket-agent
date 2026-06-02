"use client";

import { useStrategies } from "@/lib/hooks";
import { StrategyCard } from "@/components/StrategyCard";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";

export default function StrategiesPage() {
  const router = useRouter();
  const { data: strategies, loading } = useStrategies();

  if (loading && !strategies) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 animate-pulse rounded bg-gray-800" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-32 animate-pulse rounded-lg bg-gray-800/50" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <button
          onClick={() => router.push("/portfolio")}
          className="text-gray-500 hover:text-white transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <h1 className="text-xl font-bold text-white">Strategies</h1>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {(strategies || []).map((s: any) => (
          <StrategyCard key={s.agent_id} strategy={s} />
        ))}
        {(!strategies || strategies.length === 0) && (
          <div className="col-span-full text-center py-16 text-gray-500">
            <p className="text-sm">No strategy data available</p>
          </div>
        )}
      </div>
    </div>
  );
}
