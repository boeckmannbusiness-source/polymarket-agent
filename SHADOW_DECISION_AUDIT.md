# SHADOW_DECISION_AUDIT

## State Machine Definition

### OPEN
- **Entry Conditions**:
  - `ShadowLedger.record_decision` is called.
  - Required fields: `market_id`, `strategy_id`, `confidence`, `simulated_entry_price`.
  - `decision_status` initialized to `OPEN`.
- **Exit Conditions**:
  - `OutcomeClosureEngine.resolve_decision` is called with a valid `resolution_price`.
- **Allowed Transitions**:
  - `OPEN` -> `CLOSED`
- **Invalid Transitions**:
  - `OPEN` -> `RESOLVED` (Must pass through `CLOSED`)
- **Expected Timestamps**:
  - `created_at`: Time of recording.
- **Ownership Component**: `ShadowLedger`

### CLOSED
- **Entry Conditions**:
  - `OutcomeClosureEngine.resolve_decision` begins execution.
  - Current state must be `OPEN`.
- **Exit Conditions**:
  - Realized EV and win/loss calculations complete.
- **Allowed Transitions**:
  - `CLOSED` -> `RESOLVED`
- **Invalid Transitions**:
  - `CLOSED` -> `OPEN` (Irreversible)
- **Expected Timestamps**:
  - `outcome_timestamp`: Time of resolution.
- **Ownership Component**: `OutcomeClosureEngine`

### RESOLVED
- **Entry Conditions**:
  - All resolution metrics (`realized_ev`, `actual_ev`, `win_loss`) are persisted.
  - `OutcomeReceipt` is generated.
- **Exit Conditions**:
  - None (Terminal state).
- **Allowed Transitions**:
  - None.
- **Invalid Transitions**:
  - `RESOLVED` -> `CLOSED`
  - `RESOLVED` -> `OPEN`
- **Expected Timestamps**:
  - `outcome_timestamp`: Persistence time.
- **Ownership Component**: `OutcomeClosureEngine`

## State Transition Rules
1. Transitions are strictly forward-only: `OPEN` -> `CLOSED` -> `RESOLVED`.
2. Any attempt to skip a state or move backward must raise an `IllegalStateTransition` error.
3. Once `RESOLVED`, the decision record is immutable regarding its status and realized metrics.
