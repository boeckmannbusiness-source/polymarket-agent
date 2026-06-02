"use client";

import { use } from "react";
import { useRouter } from "next/navigation";
import { useTradeTimeline } from "@/lib/hooks";
import { TradeTimeline } from "@/components/TradeTimeline";
import { ArrowLeft, Clock } from "lucide-react";

export default function TradeTimelinePage({ params }: { params: Promise<{ tradeId: string }> }) {
  const { tradeId } = use(params);
  const router = useRouter();
  const { data: timeline, loading } = useTradeTimeline(tradeId);

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center gap-4">
        <button
          onClick={() => router.back()}
          className="text-gray-500 hover:text-white transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div>
          <h1 className="text-xl font-bold text-white">Trade Timeline</h1>
          <p className="text-[10px] text-gray-500 uppercase tracking-wider font-mono">ID: {tradeId}</p>
        </div>
      </div>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-6">
        <TradeTimeline
          events={timeline?.events || []}
          loading={loading}
        />
        {!loading && (!timeline?.events || timeline.events.length === 0) && (
          <div className="flex flex-col items-center justify-center py-12 text-gray-500">
            <Clock className="h-8 w-8 mb-2 opacity-30" />
            <p className="text-sm">No timeline events found for this trade</p>
          </div>
        )}
      </div>
    </div>
  );
}
