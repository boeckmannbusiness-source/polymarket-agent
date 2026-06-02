import "@testing-library/jest-dom";
import React from "react";
import { render, screen } from "@testing-library/react";

// Mock Next.js router
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn(), back: jest.fn(), prefetch: jest.fn() }),
}));

// Mock recharts
jest.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
  AreaChart: ({ children }: any) => <div>{children}</div>,
  Area: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  CartesianGrid: () => <div />,
  Tooltip: () => <div />,
  BarChart: ({ children }: any) => <div>{children}</div>,
  Bar: () => <div />,
  Cell: () => <div />,
}));

describe("StatCard", () => {
  it("renders title and value", () => {
    const { StatCard } = require("@/components/StatCard");
    render(<StatCard title="Total Equity" value="$10,000" />);
    expect(screen.getByText("Total Equity")).toBeInTheDocument();
    expect(screen.getByText("$10,000")).toBeInTheDocument();
  });

  it("shows positive change text", () => {
    const { StatCard } = require("@/components/StatCard");
    render(<StatCard title="PnL" value="+$500" color="positive" />);
    expect(screen.getByText("+$500")).toBeInTheDocument();
  });

  it("shows loading state", () => {
    const { StatCard } = require("@/components/StatCard");
    const { container } = render(<StatCard title="Loading" value="$0" loading />);
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
  });
});

describe("HealthBadge", () => {
  it("renders healthy status", () => {
    const { HealthBadge } = require("@/components/HealthBadge");
    render(<HealthBadge status="healthy" />);
    expect(screen.getByText("Healthy")).toBeInTheDocument();
  });

  it("renders degraded status", () => {
    const { HealthBadge } = require("@/components/HealthBadge");
    render(<HealthBadge status="degraded" />);
    expect(screen.getByText("Degraded")).toBeInTheDocument();
  });

  it("renders critical status", () => {
    const { HealthBadge } = require("@/components/HealthBadge");
    render(<HealthBadge status="critical" />);
    expect(screen.getByText("Critical")).toBeInTheDocument();
  });
});

describe("DriftAlertBanner", () => {
  it("renders when drift detected", () => {
    const { DriftAlertBanner } = require("@/components/DriftAlertBanner");
    render(<DriftAlertBanner driftDetected message="Order drift detected" />);
    expect(screen.getByText("Order drift detected")).toBeInTheDocument();
  });

  it("does not render when no drift", () => {
    const { DriftAlertBanner } = require("@/components/DriftAlertBanner");
    const { container } = render(<DriftAlertBanner driftDetected={false} />);
    expect(container.firstChild).toBeNull();
  });
});

describe("PositionsTable", () => {
  it("renders empty state", () => {
    const { PositionsTable } = require("@/components/PositionsTable");
    render(<PositionsTable positions={[]} />);
    expect(screen.getByText("No positions")).toBeInTheDocument();
  });

  it("renders position rows", () => {
    const { PositionsTable } = require("@/components/PositionsTable");
    const positions = [
      {
        market_id: "abc-123",
        market_slug: "test-market",
        direction: "BUY",
        size: 100,
        entry_price: 0.55,
        current_price: 0.6,
        unrealized_pnl: 5.0,
        realized_pnl: 0,
        avg_entry_price: 0.55,
        strategy: "test_strat",
      },
    ];
    render(<PositionsTable positions={positions} />);
    expect(screen.getByText("test-market")).toBeInTheDocument();
    expect(screen.getByText("BUY")).toBeInTheDocument();
    expect(screen.getByText("100.00")).toBeInTheDocument();
  });

  it("shows loading skeleton", () => {
    const { PositionsTable } = require("@/components/PositionsTable");
    const { container } = render(<PositionsTable positions={[]} loading />);
    expect(container.querySelectorAll(".animate-pulse").length).toBe(5);
  });
});

describe("TradeTimeline", () => {
  it("renders empty state", () => {
    const { TradeTimeline } = require("@/components/TradeTimeline");
    render(<TradeTimeline events={[]} />);
    expect(screen.getByText("No events recorded")).toBeInTheDocument();
  });

  it("renders ordered events", () => {
    const { TradeTimeline } = require("@/components/TradeTimeline");
    const events = [
      { event_type: "TradeCreated", event_label: "Trade Created" },
      { event_type: "OrderSubmitted", event_label: "Order #1 Submitted" },
      { event_type: "FillEvent", event_label: "Fill #1" },
      { event_type: "OrderFilled", event_label: "Order #1 Fully Filled" },
    ];
    render(<TradeTimeline events={events} />);
    expect(screen.getByText("Trade Created")).toBeInTheDocument();
    expect(screen.getByText("Order #1 Submitted")).toBeInTheDocument();
    expect(screen.getByText("Fill #1")).toBeInTheDocument();
    expect(screen.getByText("Order #1 Fully Filled")).toBeInTheDocument();
  });
});

describe("StrategyCard", () => {
  it("renders strategy KPIs", () => {
    const { StrategyCard } = require("@/components/StrategyCard");
    const strategy = {
      agent_id: "test_bot",
      total_trades: 25,
      wins: 15,
      losses: 10,
      win_rate: 60,
      cumulative_pnl: 150.0,
      realized_pnl: 150.0,
      avg_trade_duration_hours: 4.5,
      max_drawdown: 0.05,
      sharpe_ratio: 1.2,
      total_volume: 5000,
      total_fees: 12.5,
    };
    render(<StrategyCard strategy={strategy} />);
    expect(screen.getByText("test_bot")).toBeInTheDocument();
    expect(screen.getByText("60.0%")).toBeInTheDocument();
    expect(screen.getByText("1.20")).toBeInTheDocument();
  });
});

describe("ExposurePanel", () => {
  it("renders exposure metrics", () => {
    const { ExposurePanel } = require("@/components/ExposurePanel");
    render(
      <ExposurePanel
        totalLong={500}
        totalShort={200}
        netExposure={300}
        concentrationRisk={25}
        largestPositions={[]}
        exposureByMarket={[]}
      />
    );
    expect(screen.getByText("$500.00")).toBeInTheDocument();
    expect(screen.getByText("$200.00")).toBeInTheDocument();
    expect(screen.getByText("$300.00")).toBeInTheDocument();
    expect(screen.getByText("25.0%")).toBeInTheDocument();
  });
});

describe("PnLChart", () => {
  it("renders no data state", () => {
    const { PnLChart } = require("@/components/PnLChart");
    render(<PnLChart data={[]} />);
    expect(screen.getByText("No data available")).toBeInTheDocument();
  });

  it("renders with data", () => {
    const { PnLChart } = require("@/components/PnLChart");
    const data = [
      { time: "10:00", value: 100 },
      { time: "11:00", value: 105 },
    ];
    const { container } = render(<PnLChart data={data} />);
    expect(container.querySelector("div")).toBeInTheDocument();
  });
});
