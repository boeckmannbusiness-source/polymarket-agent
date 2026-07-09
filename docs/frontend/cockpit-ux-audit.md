# Trading Cockpit UX Audit

This document outlines the findings of a UX audit performed on the Polymarket Intelligence Agent's System Stability Cockpit and proposes optimized dashboard configurations for different operational contexts.

## Audit Findings

### 1. Which panels are redundant?
*   **SystemNarrative vs. SystemHealthHeader:** The `SystemHealthHeader` already contains a truncated `transition_summary`. The standalone `SystemNarrative` component provides the same information, leading to vertical clutter.
*   **DecisionBanner vs. SystemHealthHeader:** Both display the "Action" recommendation. While `DecisionBanner` provides more detailed reasoning, the primary "ACTION: [None|Monitor|Intervene]" should be centralized.
*   **PrimarySignal vs. StabilityMetricsPanel:** `PrimarySignal` isolates a single "top indicator" (like flip count), while `StabilityMetricsPanel` visualizes the same data within the "Stability" gauge. They should be merged into a single "Health Diagnostics" view.

### 2. Which metrics are not actionable?
*   **Flip Rate per Minute:** Operators cannot directly influence this; it is a derivative of system volatility. It belongs in a "Post-Mortem" view, not a "Live Ops" cockpit.
*   **Recorded Snapshots Count:** A technical debug metric that indicates database activity but provides no value for trading decisions.
*   **Hysteresis Rejected Count:** While useful for developers tuning the state machine, an operator only needs to know if the system is "Oscillating," not the specific count of rejected transitions.

### 3. Which metrics are missing for operational decision making?
*   **Liquidity/Balance Alerts:** Real-time tracking of wallet balances and gas levels. If the system is in `NORMAL` mode but has no gas, it cannot trade.
*   **Data Latency (E2E):** The delta between market event time and system processing time. High latency should trigger a `DEGRADED` mode.
*   **Active Position Risk:** Current number of open positions, total unrealized PnL, and proximity to "Max Drawdown" circuit breakers.
*   **Exchange Connectivity Health:** Granular status of WebSocket heartbeats and API rate-limit headroom.

### 4. Top 5 pieces of information needed within 3 seconds:
1.  **System Mode & Action:** (e.g., `PROTECTED` — `MONITOR`)
2.  **Current Exposure:** (Total capital at risk vs. max limit)
3.  **Active PnL:** (Open positions + daily realized profit/loss)
4.  **Primary Driver of Degradation:** (Why are we not in `NORMAL`? e.g., "High Volatility")
5.  **Connectivity Status:** (Are we receiving live data?)

---

## Ideal Dashboard Designs

### 1. Ideal Operator Dashboard (Desktop)
*Focus: Comprehensive situational awareness and pro-active monitoring.*

*   **Must-Have Widgets:**
    - **Unified Health Header:** Merged Mode, Risk, Action, and a single-line Narrative.
    - **Trading Pulse:** Open positions, Unrealized PnL, and Daily PnL gauge.
    - **System Forces (The Triad):** Gauges for Pressure (Backlog), Stability (Flips), and Throughput (Execution success).
    - **Risk Perimeter:** Exposure by strategy and proximity to circuit breakers.
    - **Manual Control Center:** Global Kill-Switch and Mode Override buttons.
*   **Nice-to-Have Widgets:**
    - **Mode Timeline:** Collapsible history for context on recent shifts.
    - **Market Context:** Macro volatility or trend indicators.
*   **Remove Candidates:**
    - `StressSimulationPanel` (Move to "Incident Lab" sub-page).
    - `PrimarySignal` (Merge into Health Header).

### 2. Ideal Mobile Dashboard
*Focus: Critical alerts and emergency intervention while on the go.*

*   **Must-Have Widgets:**
    - **System Status Card:** High-contrast color block showing Mode and recommended Action.
    - **The "Big Red Button":** Immediate Global Kill-Switch access.
    - **Risk Summary:** Total Exposure % and Daily PnL.
    - **Alert Ticker:** Last 3 critical system events.
*   **Nice-to-Have Widgets:**
    - **Mini Performance Sparkline:** 24h PnL trend.
*   **Remove Candidates:**
    - `ModeTimeline` (Too complex for small screens).
    - `StabilityMetricsPanel` (Gauges take too much space).

### 3. Ideal Emergency Dashboard
*Focus: Rapid triage and root-cause identification when the system is halted.*

*   **Must-Have Widgets:**
    - **Trigger Diagnostic:** The specific metric that tripped the circuit breaker (e.g., "Max Loss: -$500 exceeded").
    - **Kill-Switch Inventory:** Status of all automated and manual stops.
    - **Dependency Health:** Live status of Redis, Database, and External APIs.
    - **Event Audit Log:** The last 50 system logs leading up to the halt.
*   **Nice-to-Have Widgets:**
    - **State Snapshot:** Internal variable values at the moment of failure.
*   **Remove Candidates:**
    - **Market Data Feed:** Irrelevant when trading is disabled.
    - **Throughput Gauges:** Will be at zero.

---

## Implementation Strategy
1.  **Consolidate Header:** Merge `SystemNarrative` and `DecisionBanner` into `SystemHealthHeader`.
2.  **Trading Overlay:** Add a new `TradingStatePanel` to show PnL and Exposure.
3.  **Contextual Views:** Use CSS Media Queries to switch to the "Mobile" layout automatically.
4.  **Emergency Mode:** Detect `EMERGENCY_STOP` or `KILL_SWITCH` state to auto-promote the "Emergency Dashboard" widgets to the top.
