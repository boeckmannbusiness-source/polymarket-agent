# BLOCKING_REASON
Generated at: 2026-07-01T08:37:57.449591+00:00

## Blocker: NO_SIGNALS

### Runtime Summary
- **Target Runtime**: 3600s
- **Actual Runtime**: 612s
- **Chain Passes**: 11
- **Decisions Created**: 5
- **Decisions Resolved**: 5

### Chain State
| Component | Status | Evidence |
|-----------|--------|----------|
| Market Observation | NOT_CHECKED | - |
| Signal Generation | NOT_CHECKED | - |
| Decision Creation | ACTIVE | 5 decisions |
| Outcome Resolution | ACTIVE | 5 resolved |
| Evidence Generation | ACTIVE | origin=shadow |

### Validation Results
| Check | Result |
|-------|--------|
| scheduler_uptime >= target | FAIL (0:10:14.167769) |
| decision_count >= 1 | PASS (5) |
| resolved_count >= 1 | PASS (5) |
| last_decision_id != null | FAIL |
| decisions_per_hour > 0 | PASS (5) |
| origin == shadow | PASS (shadow) |

### Remediation
- No signals exist in the Signal table. The inester pipeline (PolymarketRESTIngester, PolymarketWSIngester, WhaleAgent, SignalAgent) must be running to produce signals. If external APIs are unreachable, ensure network connectivity to gamma-api.polymarket.com and that the background task loops (rest_ingester, ws_ingester, signal_agent) are active. Owner: ingress/agent team.

### Next Actions
1. Fix the blocking component
2. Re-run collect_runtime_evidence.py
3. Verify RuntimeEvidenceValidator returns RUNTIME_READY
