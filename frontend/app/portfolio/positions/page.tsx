"use client";

import { useState } from "react";
import { usePositions } from "@/lib/hooks";
import { PositionsTable } from "@/components/PositionsTable";
import { cn } from "@/lib/utils";

const TABS = ["ALL", "OPEN", "CLOSED"] as const;

export default function PositionsPage() {
  const [tab, setTab] = useState<string>("OPEN");
  const { data: positions, loading } = usePositions(tab === "ALL" ? undefined : tab);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-white">Positions</h1>
      </div>

      <div className="flex gap-1 rounded-lg border border-[var(--border)] p-1 w-fit">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "px-3 py-1.5 text-xs font-bold rounded transition-colors",
              tab === t
                ? "bg-[var(--primary)] text-white"
                : "text-gray-500 hover:text-gray-300",
            )}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)]">
        <PositionsTable positions={positions || []} loading={loading} />
      </div>
    </div>
  );
}
