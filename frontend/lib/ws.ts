type EventCallback = (event: any) => void;

type WsStatus = "connecting" | "connected" | "disconnected" | "reconnecting";

interface WsClientOptions {
  url: string;
  onEvent?: EventCallback;
  onStatusChange?: (status: WsStatus) => void;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

export class WsClient {
  private ws: WebSocket | null = null;
  private options: WsClientOptions;
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private handlers: Map<string, Set<EventCallback>> = new Map();
  private _status: WsStatus = "disconnected";

  constructor(options: WsClientOptions) {
    this.options = {
      reconnectInterval: 3000,
      maxReconnectAttempts: 10,
      ...options,
    };
  }

  get status() {
    return this._status;
  }

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) return;
    this.setStatus("connecting");

    try {
      this.ws = new WebSocket(this.options.url);
    } catch (e) {
      console.error("WebSocket connection failed:", e);
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.setStatus("connected");
      this.startPing();
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "pong") return;
        this.options.onEvent?.(data);
        this.dispatch(data.type, data);
        this.dispatch("*", data);
      } catch (e) {
        console.warn("WS parse error:", e);
      }
    };

    this.ws.onclose = () => {
      this.setStatus("disconnected");
      this.stopPing();
      this.scheduleReconnect();
    };

    this.ws.onerror = () => {
      this.setStatus("reconnecting");
    };
  }

  disconnect() {
    this.reconnectAttempts = this.options.maxReconnectAttempts!;
    this.stopPing();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
    this.ws = null;
    this.setStatus("disconnected");
  }

  send(data: any) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  on(eventType: string, callback: EventCallback) {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, new Set());
    }
    this.handlers.get(eventType)!.add(callback);
    return () => this.handlers.get(eventType)?.delete(callback);
  }

  private dispatch(eventType: string, data: any) {
    this.handlers.get(eventType)?.forEach((cb) => cb(data));
  }

  private setStatus(status: WsStatus) {
    this._status = status;
    this.options.onStatusChange?.(status);
  }

  private scheduleReconnect() {
    if (this.reconnectAttempts >= this.options.maxReconnectAttempts!) return;
    this.setStatus("reconnecting");
    this.reconnectTimer = setTimeout(() => {
      this.reconnectAttempts++;
      this.connect();
    }, this.options.reconnectInterval);
  }

  private startPing() {
    this.stopPing();
    this.pingTimer = setInterval(() => {
      this.send("ping");
    }, 30000);
  }

  private stopPing() {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
  }
}

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export function createPortfolioClient(onEvent?: EventCallback, onStatusChange?: (s: WsStatus) => void) {
  return new WsClient({ url: `${WS_BASE}/ws/portfolio`, onEvent, onStatusChange });
}

export function createTradesClient(tradeIds?: string[], onEvent?: EventCallback) {
  const params = tradeIds?.length ? `?trade_ids=${tradeIds.join(",")}` : "";
  return new WsClient({ url: `${WS_BASE}/ws/trades${params}`, onEvent });
}

export function createFillsClient(marketIds?: string[], onEvent?: EventCallback) {
  const params = marketIds?.length ? `?market_ids=${marketIds.join(",")}` : "";
  return new WsClient({ url: `${WS_BASE}/ws/fills${params}`, onEvent });
}

export function createMonitoringClient(onEvent?: EventCallback) {
  return new WsClient({ url: `${WS_BASE}/ws/monitoring`, onEvent });
}

export function createAlertsClient(onEvent?: EventCallback) {
  return new WsClient({ url: `${WS_BASE}/ws/alerts`, onEvent });
}
