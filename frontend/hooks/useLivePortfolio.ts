"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { createPortfolioClient } from "@/lib/ws";
import { api } from "@/lib/api";
import { eventApplier, shouldRefetchOnGap, WsEvent } from "@/lib/eventApplier";

export function useLivePortfolio() {
  const [state, setState] = useState<{
    snapshot: any;
    positions: any[];
    orders: any[];
    alerts: any[];
    trades: any[];
  }>({ snapshot: null, positions: [], orders: [], alerts: [], trades: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isLive, setIsLive] = useState(false);
  const lastSequence = useRef<number>(0);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const wsRef = useRef<any>(null);
  const disconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchSnapshot = useCallback(async () => {
    try {
      setError(null);
      const [snapshot, positions] = await Promise.all([
        api.portfolio.summary(),
        api.portfolio.positions("OPEN"),
      ]);
      setState((prev) => ({
        ...prev,
        snapshot,
        positions: positions || [],
      }));
    } catch (e: any) {
      setError(e?.message || "Failed to fetch");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSnapshot();

    const ws = createPortfolioClient((event: any) => {
      const seq = event.sequence || 0;
      if (lastSequence.current > 0 && shouldRefetchOnGap(lastSequence.current, seq)) {
        fetchSnapshot();
      }
      lastSequence.current = seq;

      setState((prev) => eventApplier.apply(event as WsEvent, prev));
    });
    wsRef.current = ws;
    ws.connect();

    const statusCheck = setInterval(() => {
      const live = ws.status === "connected";
      setIsLive(live);

      if (!live) {
        if (!disconnectTimer.current) {
          disconnectTimer.current = setTimeout(() => {
            fetchSnapshot();
          }, 10000);
        }
      } else {
        if (disconnectTimer.current) {
          clearTimeout(disconnectTimer.current);
          disconnectTimer.current = null;
        }
      }
    }, 1000);

    pollingRef.current = setInterval(() => {
      if (ws.status !== "connected") {
        fetchSnapshot();
      }
    }, 15000);

    return () => {
      ws.disconnect();
      if (pollingRef.current) clearInterval(pollingRef.current);
      clearInterval(statusCheck);
      if (disconnectTimer.current) clearTimeout(disconnectTimer.current);
    };
  }, [fetchSnapshot]);

  return { ...state, loading, error, isLive, refetch: fetchSnapshot };
}

export function useLivePositions() {
  const [positions, setPositions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    try {
      const data = await api.portfolio.positions("OPEN");
      setPositions(data || []);
    } catch {
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
    const ws = createPortfolioClient((event: any) => {
      if (event.event_type === "fill.created") {
        fetch();
      }
    });
    ws.connect();

    const interval = setInterval(fetch, 10000);

    return () => {
      ws.disconnect();
      clearInterval(interval);
    };
  }, [fetch]);

  return { positions, loading };
}
