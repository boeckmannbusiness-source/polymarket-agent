# Live Validation Experiment: Expertise-Weighted Following

## 1. Experiment Overview
This experiment framework is designed to validate the theoretical uplift of 'Expertise-Weighted Following' against the current production 'Whale Following' baseline in a live, micro-capital environment.

---

## 2. Experimental Design

### Strategy Variants (Parallel Execution)
1.  **Baseline (A)**: Standard `WhaleFollowingStrategy` using raw wallet scores and sizes.
2.  **Experimental (B)**: `ExpertiseWeightedStrategy` (new) which gates signals by inferred category expertise.
3.  **Control (C)**: `RandomWhaleFollower` which follows a random sample of active whales to establish a noise floor.

### Operational Constraints
*   **Position Sizing**: Fixed at $1.00 - $5.00 per trade to minimize capital risk.
*   **Risk Controls**: All variants subject to the same `SafetyService` circuit breakers and `GlobalRiskGuard` limits.
*   **Execution**: Full production pipeline (`TradeService` -> `PolygonRPC`) with no simulation shortcuts.

---

## 3. Instrumentation & Metrics

The experiment will use the `correlation_id` to trace every signal from generation to final PnL.

| Metric | Measurement Method | Target |
| :--- | :--- | :--- |
| **Real PnL** | `Trade.pnl` (Net of all fees) | Compare A vs B vs C |
| **Fill Rate** | `Trade.filled_size / Trade.requested_size` | Verify execution liquidity |
| **Latency** | `Trade.execution_ms` | Measure impact of expertise lookup |
| **Divergence** | `Real PnL - ReplayEngine Predicted PnL` | Identify simulation bias |
| **Stability** | `Sharpe / Variance` by category | Measure domain robustness |
| **Price Alpha** | `Theoretical Price - Actual Fill Price` | Separate Signal vs. Execution quality |

---

## 4. Signal vs. Execution Quality Separation

To prevent misattributing execution advantages as strategy alpha, we will instrument three distinct price points for every signal:

1.  **Theoretical Entry Price**: The mid-price at the exact millisecond the signal was generated (Strategy Alpha).
2.  **Actual Fill Price**: The volume-weighted average price (VWAP) achieved by the execution pipeline.
3.  **Optimal Window Price**: The best available price (bid/ask) within a 30-second window following the signal.

### Attribution Logic
- **Signal Quality**: `(Final Price - Theoretical Price) / Theoretical Price`
- **Execution Efficiency**: `(Theoretical Price - Actual Price) / Theoretical Price`
- **Execution Opportunity Cost**: `(Actual Price - Optimal Window Price) / Theoretical Price`

---

## 5. Implementation Plan

### Phase 1: Instrumentation (Days 1-2)
- Add `experimental_group` tag to the `Signal` and `Trade` models.
- Update `SignalService` to persist `expertise_domain` and `expertise_score` at the moment of generation.

### Phase 2: Experimental Strategies (Days 3-5)
- Implement `ExpertiseWeightedStrategy` inheriting from `BaseStrategy`.
- Implement `RandomControlStrategy`.
- Configure `PortfolioAllocator` to split $100.00 capital across the three groups.

### Phase 3: Launch & Monitoring (Week 1)
- Deploy in "Shadow" mode for 48 hours to verify signal generation.
- Transition to "Active" mode with micro-positions.

### Phase 4: Analysis (Weeks 2-4)
- Weekly robustness audits.
- Final go/no-go recommendation for architectural refactor.

---

## 6. Success Criteria for Refactor
Architectural refactor to the 'Expertise Registry' model will proceed only if:
1.  **Expertise Following (B)** shows >15% higher Profit Factor than **Standard (A)**.
2.  **Signal Divergence** is <10% compared to ReplayEngine predictions.
3.  **Experimental Sharpe** is >1.5 over a minimum of 200 trades.
