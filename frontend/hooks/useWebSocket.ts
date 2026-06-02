"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { WsClient, createPortfolioClient, createAlertsClient, createMonitoringClient } from "@/lib/ws";
import { api } from "@/lib/api";
import { eventApplier, shouldRefetchOnGap, WsEvent } from "@/lib/eventApplier";

type WsStatus = "connecting" | "connected" | "disconnected" | "reconnecting";

function jitter(base: number): number {
  return base + Math.random() * base * 0.3;
}

export function useWebSocket(client: WsClient | null, onGapDetected?: () => void) {
  const [status, setStatus] = useState<WsStatus>("disconnected");
  const statusRef = useRef<WsStatus>("disconnected");
  const disconnTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSequence = useRef<number>(0);

  useEffect(() => {
    if (!client) return;

    const interval = setInterval(() => {
      const s = client.status;
      if (s !== statusRef.current) {
        statusRef.current = s;
        setStatus(s);

        if (s === "disconnected" || s === "reconnecting") {
          disconnTimer.current = setTimeout(() => {
            onGapDetected?.();
          }, 10000);
        } else {
          if (disconnTimer.current) {
            clearTimeout(disconnTimer.current);
            disconnTimer.current = null;
          }
        }
      }
    }, 500);

    client.connect();

    return () => {
      clearInterval(interval);
      if (disconnTimer.current) clearTimeout(disconnTimer.current);
    };
  }, [client, onGapDetected]);

  return { status, isLive: status === "connected" };
}

export function usePortfolioWs(onEvent?: (event: any) => void) {
  const clientRef = useRef<WsClient | null>(null);

  useEffect(() => {
    const client = createPortfolioClient(
      (event) => {
        if (event.event_type === "portfolio.snapshot" || event.event_type === "pnl.updated") {
          onEvent?.(event);
        }
      },
    );
    clientRef.current = client;
    client.connect();

    return () => client.disconnect();
  }, [onEvent]);

  return { status: "connected" as WsStatus, isLive: true };
}

export function useAlertsWs() {
  const clientRef = useRef<WsClient | null>(null);
  const [alerts, setAlerts] = useState<any[]>([]);

  useEffect(() => {
    const client = createAlertsClient((event) => {
      setAlerts((prev) => {
        if (prev.some((a) => a.id === event.event_id)) return prev;
        return [event, ...prev].slice(0, 200);
      });
    });
    clientRef.current = client;
    client.connect();
    return () => client.disconnect();
  }, []);

  const { status } = useWebSocket(clientRef.current);

  const acknowledge = useCallback((alertId: string) => {
    setAlerts((prev) => prev.map((a) => (a.id === alertId ? { ...a, acknowledged: true } : a)));
  }, []);

  const dismiss = useCallback((alertId: string) => {
    setAlerts((prev) => prev.map((a) => (a.id === alertId ? { ...a, status: "resolved" } : a)));
  }, []);

  return { alerts, status, isLive: status === "connected", acknowledge, dismiss };
}

export function useMonitoringWs() {
  const clientRef = useRef<WsClient | null>(null);
  const [driftEvents, setDriftEvents] = useState<any[]>([]);

  const handleGap = useCallback(() => {
  }, []);

  useEffect(() => {
    const client = createMonitoringClient((event) => {
      if (event.event_type === "drift.detected" || event.event_type === "execution.error") {
        setDriftEvents((prev) => [event, ...prev].slice(0, 100));
      }
    });
    clientRef.current = client;
    client.connect();
    return () => client.disconnect();
  }, []);

  const { status } = useWebSocket(clientRef.current, handleGap);
  return { driftEvents, status, isLive: status === "connected" };
}
