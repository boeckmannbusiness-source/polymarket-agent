"use client";

import { cn } from "@/lib/utils";
import {
  Clock, CheckCircle2, XCircle, Loader2, Send, AlertTriangle,
} from "lucide-react";

export interface TimelineEvent {
  event_type: string;
  event_label: string;
  timestamp?: string | null;
  order_id?: string | null;
  fill_id?: string | null;
  size?: number | null;
  price?: number | null;
  status?: string | null;
  details?: Record<string, any> | null;
}

interface TradeTimelineProps {
  events: TimelineEvent[];
  loading?: boolean;
}

const eventIcons: Record<string, any> = {
  TradeCreated: Send,
  OrderSubmitted: Loader2,
  OrderPartiallyFilled: Clock,
  FillEvent: CheckCircle2,
  OrderFilled: CheckCircle2,
  OrderCancelled: XCircle,
  OrderFailed: AlertTriangle,
};

const eventColors: Record<string, string> = {
  TradeCreated: "text-blue-500",
  OrderSubmitted: "text-yellow-500",
  OrderPartiallyFilled: "text-yellow-500",
  FillEvent: "text-emerald-500",
  OrderFilled: "text-emerald-500",
  OrderCancelled: "text-rose-500",
  OrderFailed: "text-rose-500",
};

const eventBgColors: Record<string, string> = {
  TradeCreated: "border-blue-500/30 bg-blue-500/5",
  OrderSubmitted: "border-yellow-500/30 bg-yellow-500/5",
  OrderPartiallyFilled: "border-yellow-500/30 bg-yellow-500/5",
  FillEvent: "border-emerald-500/30 bg-emerald-500/5",
  OrderFilled: "border-emerald-500/30 bg-emerald-500/10",
  OrderCancelled: "border-rose-500/30 bg-rose-500/5",
  OrderFailed: "border-rose-500/30 bg-rose-500/10",
};

export function TradeTimeline({ events, loading }: TradeTimelineProps) {
  if (loading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="flex gap-3">
            <div className="h-8 w-8 animate-pulse rounded-full bg-gray-800" />
            <div className="flex-1 space-y-1">
              <div className="h-4 w-32 animate-pulse rounded bg-gray-800" />
              <div className="h-3 w-48 animate-pulse rounded bg-gray-800/50" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (!events || events.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-gray-500">
        <Clock className="h-8 w-8 mb-2 opacity-30" />
        <p className="text-sm">No events recorded</p>
      </div>
    );
  }

  return (
    <div className="relative">
      <div className="absolute left-4 top-3 bottom-3 w-px bg-gray-800" />
      <div className="space-y-0">
        {events.map((event, i) => {
          const Icon = eventIcons[event.event_type] || Clock;
          const color = eventColors[event.event_type] || "text-gray-400";
          const bg = eventBgColors[event.event_type] || "border-gray-800 bg-gray-900/30";

          return (
            <div key={i} className={cn("relative flex gap-4 pb-4", "pl-10")}>
              <div className={cn(
                "absolute left-2.5 flex h-4 w-4 items-center justify-center rounded-full border",
                bg,
              )}>
                <Icon className={cn("h-2.5 w-2.5", color)} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-bold text-white">{event.event_label}</span>
                  {event.status && (
                    <span className={cn(
                      "rounded px-1.5 py-0.5 text-[9px] font-bold uppercase",
                      event.status === "filled" || event.status === "open"
                        ? "bg-emerald-900/40 text-emerald-400"
                        : event.status === "cancelled" || event.status === "failed"
                        ? "bg-rose-900/40 text-rose-400"
                        : "bg-gray-800 text-gray-400",
                    )}>
                      {event.status}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-3 text-[10px] text-gray-500 mt-0.5">
                  {event.timestamp && (
                    <span>{new Date(event.timestamp).toLocaleString()}</span>
                  )}
                  {event.size != null && (
                    <span>Size: {event.size.toFixed(2)}</span>
                  )}
                  {event.price != null && (
                    <span>@ {event.price.toFixed(4)}</span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
