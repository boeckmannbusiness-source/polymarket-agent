# SANDBOX_PROMOTION_POLICY

## Purpose
Define the quantitative and qualitative requirements for promoting a strategy from Shadow Validation to Sandbox Execution.

## Promotion Requirements

### 1. Decision Volume
- **Requirement**: Minimum 500 shadow decisions recorded in the `ShadowDecisionLog`.
- **Rationale**: Ensures statistical significance of performance metrics.

### 2. Replay Parity
- **Requirement**: ≥95% replay parity across all recorded decisions.
- **Rationale**: Guarantees that decisions made in real-time are reproducible offline, ensuring system determinism.

### 3. Performance (EV)
- **Requirement**: Positive realized Expected Value (EV) over the evaluation period.
- **Rationale**: Validates that the intelligence pipeline produces economically viable decisions.

### 4. Certification Integrity
- **Requirement**: Zero certification revocations or safety invariant violations during the shadow period.
- **Rationale**: Maintains the strict safety boundaries required for sandbox operations.

### 5. Confidence Calibration
- **Requirement**: Stable confidence calibration (Brier Score ≤ 0.25).
- **Rationale**: Ensures that the strategy's self-reported confidence is a reliable indicator of outcome probability.

## Promotion Process

1. **Evaluation**: `OutcomeEvaluator` runs a full audit of the strategy's shadow performance.
2. **Review**: Stability tests must pass with 100% success rate.
3. **Approval**: If all thresholds are met, the strategy is marked as `READY` for Sandbox promotion.

## Status: NOT READY
- **Reason**: Initial policy deployment. Shadow data collection in progress.
