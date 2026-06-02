"use client";

import { useState } from "react";
import { useAlertsWs } from "@/hooks/useWebSocket";
import { LiveIndicator } from "@/components/LiveIndicator";

export function AlertCenter() {
  const { alerts, status, isLive, acknowledge, dismiss } = useAlertsWs();
  const [open, setOpen] = useState(false);

  const severityColor: Record<string, string> = {
    critical: "border-red-500 bg-red-950",
    warning: "border-amber-500 bg-amber-950",
    info: "border-blue-500 bg-blue-950",
  };

  const unacknowledged = alerts.filter((a) => !a.acknowledged).length;

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="relative flex items-center gap-2 px-3 py-1 text-sm border border-border rounded hover:bg-accent"
      >
        <LiveIndicator status={status} label="" />
        Alerts
        {unacknowledged > 0 && (
          <span className="inline-flex items-center justify-center w-5 h-5 text-xs font-bold text-white bg-red-600 rounded-full">
            {unacknowledged}
          </span>
        )}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-2 z-50 w-96 max-h-[70vh] overflow-y-auto border border-border rounded-lg bg-background shadow-2xl">
            <div className="sticky top-0 flex items-center justify-between p-3 border-b border-border bg-background">
              <span className="text-sm font-semibold">Alert Feed</span>
              <LiveIndicator status={status} />
            </div>

            {alerts.length === 0 && (
              <div className="p-8 text-center text-sm text-muted-foreground">
                No alerts
              </div>
            )}

            {alerts.map((alert) => (
              <div
                key={alert.id}
                className={`p-3 border-l-4 ${severityColor[alert.severity] || "border-muted"} border-b border-border/50 ${alert.acknowledged ? "opacity-60" : ""}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-mono uppercase text-muted-foreground">
                        {alert.severity}
                      </span>
                      <span className="text-xs font-mono text-muted-foreground">
                        {alert.category}
                      </span>
                    </div>
                    <p className="text-sm font-medium truncate">{alert.title}</p>
                    <p className="text-xs text-muted-foreground mt-1">{alert.message}</p>
                    <p className="text-[10px] text-muted-foreground mt-1">
                      {new Date(alert.timestamp).toLocaleTimeString()}
                    </p>
                  </div>
                  <div className="flex gap-1 shrink-0">
                    {!alert.acknowledged && (
                      <button
                        onClick={() => acknowledge(alert.id)}
                        className="px-2 py-0.5 text-xs border border-border rounded hover:bg-accent"
                      >
                        Ack
                      </button>
                    )}
                    <button
                      onClick={() => dismiss(alert.id)}
                      className="px-2 py-0.5 text-xs border border-border rounded hover:bg-accent"
                    >
                      ✕
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
