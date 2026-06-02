import { api } from "@/lib/api";

export interface WsEvent {
  event_id: string;
  sequence: number;
  entity_type: string;
  entity_id: string;
  event_type: string;
  timestamp: string;
  payload: Record<string, any>;
}

export interface PortfolioSnapshot {
  total_equity: number;
  net_exposure: number;
  unrealized_pnl: number;
  realized_pnl: number;
  drawdown: number;
  open_positions_count: number;
  strategy_breakdown: Array<{
    agent_id: string;
    total_pnl: number;
    trade_count: number;
    win_rate: number;
  }>;
}

export interface Position {
  trade_id: string;
  market_id: string;
  side: string;
  size: number;
  filled_size: number;
  price: number;
  pnl: number;
  status: string;
}

export interface AlertEvent {
  id: string;
  rule: string;
  severity: string;
  category: string;
  title: string;
  message: string;
  entity_id: string;
  timestamp: string;
  status: string;
  acknowledged: boolean;
}

export interface FillEvent {
  fill_id: string;
  trade_id: string;
  market_id: string;
  side: string;
  outcome: string;
  size: number;
  price: number;
  fee: number;
  filled_at: string;
}

export interface OrderEvent {
  order_id: string;
  trade_id: string;
  status: string;
  side: string;
  size: number;
  filled_size: number;
  price: number | null;
}

export interface TradeEvent {
  trade_id: string;
  market_id: string;
  status: string;
  side: string;
  size: number;
  agent_id: string;
}

export class EventApplier {
  apply(
    event: WsEvent,
    state: {
      snapshot: PortfolioSnapshot | null;
      positions: Position[];
      orders: any[];
      alerts: AlertEvent[];
      trades: any[];
    },
  ): {
    snapshot: PortfolioSnapshot | null;
    positions: Position[];
    orders: any[];
    alerts: AlertEvent[];
    trades: any[];
  } {
    switch (event.event_type) {
      case "fill.created":
        return this._applyFill(event, state);
      case "order.updated":
        return this._applyOrder(event, state);
      case "trade.updated":
        return this._applyTrade(event, state);
      case "portfolio.snapshot":
        return this._applySnapshot(event, state);
      case "pnl.updated":
        return this._applyPnl(event, state);
      case "alert.created":
        return this._applyAlert(event, state);
      default:
        return state;
    }
  }

  private _applyFill(event: WsEvent, state: any) {
    const fill = event.payload as FillEvent;
    const existingIdx = state.positions.findIndex(
      (p: any) => p.trade_id === fill.trade_id,
    );
    const newPositions = [...state.positions];
    if (existingIdx >= 0) {
      newPositions[existingIdx] = {
        ...newPositions[existingIdx],
        filled_size: fill.size,
        price: fill.price,
      };
    } else {
      newPositions.unshift({
        trade_id: fill.trade_id,
        market_id: fill.market_id,
        side: fill.side,
        size: fill.size,
        filled_size: fill.size,
        price: fill.price,
        pnl: 0,
        status: "open",
      });
    }
    return { ...state, positions: newPositions };
  }

  private _applyOrder(event: WsEvent, state: any) {
    const order = event.payload as OrderEvent;
    const existingIdx = state.orders.findIndex(
      (o: any) => o.order_id === order.order_id,
    );
    const newOrders = [...state.orders];
    if (existingIdx >= 0) {
      newOrders[existingIdx] = { ...newOrders[existingIdx], ...order };
    } else {
      newOrders.unshift(order);
    }
    return { ...state, orders: newOrders };
  }

  private _applyTrade(event: WsEvent, state: any) {
    const trade = event.payload as TradeEvent;
    const existingIdx = state.trades.findIndex(
      (t: any) => t.trade_id === trade.trade_id,
    );
    const newTrades = [...state.trades];
    if (existingIdx >= 0) {
      newTrades[existingIdx] = { ...newTrades[existingIdx], ...trade };
    } else {
      newTrades.unshift(trade);
    }
    return { ...state, trades: newTrades };
  }

  private _applySnapshot(event: WsEvent, state: any) {
    return { ...state, snapshot: event.payload as PortfolioSnapshot };
  }

  private _applyPnl(event: WsEvent, state: any) {
    if (!state.snapshot) return state;
    return {
      ...state,
      snapshot: { ...state.snapshot, ...event.payload },
    };
  }

  private _applyAlert(event: WsEvent, state: any) {
    const alert = { ...event.payload, id: event.event_id } as AlertEvent;
    const existing = state.alerts.find((a: any) => a.id === alert.id);
    if (existing) return state;
    return {
      ...state,
      alerts: [alert, ...state.alerts].slice(0, 200),
    };
  }
}

export const eventApplier = new EventApplier();

export function shouldRefetchOnGap(
  lastSequence: number,
  currentSequence: number,
): boolean {
  const gap = currentSequence - lastSequence;
  return gap > 10 || gap < 0;
}
