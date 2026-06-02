import { eventApplier, shouldRefetchOnGap } from "@/lib/eventApplier";

describe("EventApplier", () => {
  const baseState = {
    snapshot: null,
    positions: [],
    orders: [],
    alerts: [],
    trades: [],
  };

  it("applies fill.created to positions", () => {
    const fillEvent = {
      event_id: "fill-1",
      sequence: 1,
      entity_type: "fill",
      entity_id: "fill-1",
      event_type: "fill.created",
      timestamp: new Date().toISOString(),
      payload: {
        fill_id: "fill-1",
        trade_id: "trade-1",
        market_id: "market-1",
        side: "BUY",
        outcome: "YES",
        size: 100,
        price: 0.55,
        fee: 0.5,
        filled_at: new Date().toISOString(),
      },
    };

    const result = eventApplier.apply(fillEvent, baseState);
    expect(result.positions).toHaveLength(1);
    expect(result.positions[0].trade_id).toBe("trade-1");
    expect(result.positions[0].filled_size).toBe(100);
  });

  it("updates existing position on second fill", () => {
    const state = {
      ...baseState,
      positions: [{
        trade_id: "trade-1",
        market_id: "market-1",
        side: "BUY",
        size: 50,
        filled_size: 50,
        price: 0.55,
        pnl: 0,
        status: "open",
      }],
    };

    const fillEvent = {
      event_id: "fill-2",
      sequence: 2,
      entity_type: "fill",
      entity_id: "fill-2",
      event_type: "fill.created",
      timestamp: new Date().toISOString(),
      payload: {
        fill_id: "fill-2",
        trade_id: "trade-1",
        market_id: "market-1",
        side: "BUY",
        outcome: "YES",
        size: 150,
        price: 0.60,
        fee: 0.5,
        filled_at: new Date().toISOString(),
      },
    };

    const result = eventApplier.apply(fillEvent, state);
    expect(result.positions).toHaveLength(1);
    expect(result.positions[0].filled_size).toBe(150);
    expect(result.positions[0].price).toBe(0.60);
  });

  it("applies order.updated correctly", () => {
    const orderEvent = {
      event_id: "ord-1",
      sequence: 1,
      entity_type: "order",
      entity_id: "ord-1",
      event_type: "order.updated",
      timestamp: new Date().toISOString(),
      payload: {
        order_id: "ord-1",
        trade_id: "trade-1",
        status: "filled",
        side: "BUY",
        size: 100,
        filled_size: 100,
        price: 0.55,
      },
    };

    const result = eventApplier.apply(orderEvent, baseState);
    expect(result.orders).toHaveLength(1);
    expect(result.orders[0].status).toBe("filled");
  });

  it("applies portfolio.snapshot as replacement", () => {
    const snapshotEvent = {
      event_id: "snap-1",
      sequence: 1,
      entity_type: "portfolio",
      entity_id: "overview",
      event_type: "portfolio.snapshot",
      timestamp: new Date().toISOString(),
      payload: {
        total_equity: 50000,
        net_exposure: 15000,
        unrealized_pnl: 500,
        realized_pnl: 1200,
        drawdown: 0.05,
        open_positions_count: 3,
        strategy_breakdown: [],
      },
    };

    const result = eventApplier.apply(snapshotEvent, baseState);
    expect(result.snapshot).toBeTruthy();
    expect(result.snapshot!.total_equity).toBe(50000);
    expect(result.snapshot!.drawdown).toBe(0.05);
  });

  it("applies pnl.updated as merge into snapshot", () => {
    const state = {
      ...baseState,
      snapshot: {
        total_equity: 50000,
        unrealized_pnl: 500,
        realized_pnl: 1200,
      },
    };

    const pnlEvent = {
      event_id: "pnl-1",
      sequence: 2,
      entity_type: "portfolio",
      entity_id: "pnl",
      event_type: "pnl.updated",
      timestamp: new Date().toISOString(),
      payload: { unrealized_pnl: 750, realized_pnl: 1300 },
    };

    const result = eventApplier.apply(pnlEvent, state);
    expect(result.snapshot!.unrealized_pnl).toBe(750);
    expect(result.snapshot!.realized_pnl).toBe(1300);
    expect(result.snapshot!.total_equity).toBe(50000);
  });

  it("applies alert.created without duplicates", () => {
    const alertEvent = {
      event_id: "alert-1",
      sequence: 1,
      entity_type: "alert",
      entity_id: "portfolio",
      event_type: "alert.created",
      timestamp: new Date().toISOString(),
      payload: {
        id: "alert-1",
        title: "Drawdown breach",
        message: "Drawdown exceeds limit",
        severity: "critical",
      },
    };

    const result1 = eventApplier.apply(alertEvent, baseState);
    expect(result1.alerts).toHaveLength(1);

    const result2 = eventApplier.apply(alertEvent, result1);
    expect(result2.alerts).toHaveLength(1);
  });

  it("does not modify state for unknown event type", () => {
    const unknownEvent = {
      event_id: "unknown-1",
      sequence: 1,
      entity_type: "unknown",
      entity_id: "x",
      event_type: "something.unknown",
      timestamp: new Date().toISOString(),
      payload: {},
    };

    const result = eventApplier.apply(unknownEvent, baseState);
    expect(result).toEqual(baseState);
  });

  it("caps alerts at 200", () => {
    let state = { ...baseState };
    for (let i = 0; i < 250; i++) {
      state = eventApplier.apply(
        {
          event_id: `alert-${i}`,
          sequence: i,
          entity_type: "alert",
          entity_id: "portfolio",
          event_type: "alert.created",
          timestamp: new Date().toISOString(),
          payload: { title: `Alert ${i}`, severity: "info" },
        },
        state,
      );
    }
    expect(state.alerts.length).toBeLessThanOrEqual(200);
  });
});

describe("shouldRefetchOnGap", () => {
  it("returns true when gap > 10", () => {
    expect(shouldRefetchOnGap(5, 20)).toBe(true);
  });

  it("returns true when sequence decreases", () => {
    expect(shouldRefetchOnGap(50, 10)).toBe(true);
  });

  it("returns false for small forward gaps", () => {
    expect(shouldRefetchOnGap(10, 12)).toBe(false);
  });

  it("returns false when lastSequence is 0", () => {
    expect(shouldRefetchOnGap(0, 5)).toBe(false);
  });
});
