"use client";

import { cn } from "@/lib/utils";
import { AlertTriangle, X } from "lucide-react";
import { useState } from "react";

interface DriftAlertBannerProps {
  driftDetected: boolean;
  message?: string;
  issues?: string[];
}

export function DriftAlertBanner({ driftDetected, message, issues }: DriftAlertBannerProps) {
  const [dismissed, setDismissed] = useState(false);

  if (!driftDetected || dismissed) return null;

  return (
    <div className="rounded-lg border border-rose-900/50 bg-rose-950/10 p-3 mb-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2">
          <AlertTriangle className="h-4 w-4 text-rose-500 mt-0.5 shrink-0" />
          <div>
            <span className="text-xs font-bold text-rose-400 uppercase tracking-wider">
              {message || "Drift Detected"}
            </span>
            {issues && issues.length > 0 && (
              <ul className="mt-1 space-y-0.5">
                {issues.map((issue, i) => (
                  <li key={i} className="text-[10px] text-rose-300/70">{issue}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
        <button
          onClick={() => setDismissed(true)}
          className="text-rose-500/50 hover:text-rose-400 transition-colors"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
