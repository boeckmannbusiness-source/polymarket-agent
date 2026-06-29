# PROMOTION_REPORT: empty_strat
Generated at: 2026-06-29T12:40:00.257647
Snapshot Hash: 6a77fa59a3bc68a5d5817e187fe0332650c962541c579da81389e58e52d9a472
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
