# RISK_GOVERNANCE_REPORT.md

## Risk Governance Implementation Report

### Overview
Risk governance in Sprint 2.3B introduces a multi-layered check system to evaluate trade intents before any hypothetical execution. This layer is situated after simulation and admission.

### Governance Layers

1.  **Capital Policy**: Enforces hard limits (position size, daily loss, exposure).
2.  **Exposure Model**: Calculates risk scores and exposure ratios based on planned positions.
3.  **Capital Governor**: Orchestrates policy and exposure checks to produce a `CapitalDecision`.
4.  **Capital Guard**: A final circuit breaker that enforces the global `capital_enabled = False` state.

### Determinism
All risk decisions are captured in a `RiskReceipt` with a `risk_hash`. The hash includes:
- `policy_version`
- `capital_decision`
- `risk_snapshot` (all inputs used for the decision)
- `reason_codes`

### Audit Trail
Every `RiskReceipt` contains a `risk_id` and a snapshot of the state at the time of the decision, ensuring full auditability of কেন (why) a trade was allowed or blocked.
