# PROMOTION_REPORT: empty_strat
Generated at: 2026-06-29T13:28:31.688059
Snapshot Hash: 2e03452d563d5a8e0c0d2283ca6a2cd8a07934f3bebe5004d07212b6992e5409
Status: **NOT_READY**

## Policy Evaluation
### Blocking Reasons
- Insufficient decision volume: 0 < 500
- Replay parity below threshold: 0.00% < 95%
- Positive realized EV required: 0.0000
- Confidence calibration unstable (Brier Score): 1.0000 > 0.25
- Promotion requires real shadow evidence: current origin is synthetic
- Origin 'synthetic' is strictly rejected for READY status.

## Key Metrics
| Metric | Value | Threshold | Result |
|--------|-------|-----------|--------|
| Resolved Decision Count | 0 | 500 | FAIL |
| Replay Parity | NOT_AVAILABLE | 95% | FAIL |
| Realized EV | NOT_AVAILABLE | > 0.0000 | FAIL |
| Brier Score | NOT_AVAILABLE | ≤ 0.25 | FAIL |
| Data Origin | synthetic | shadow | FAIL |
