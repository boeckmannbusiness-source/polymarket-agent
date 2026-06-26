# CAPITAL_POLICY.md

## Capital Policy Framework (Sprint 2.3B)

This document outlines the deterministic capital governance policy used by the `CapitalGovernor`.

### Policy Goals
- Prevent accidental capital deployment during Sandbox phase.
- Enforce strict risk boundaries for simulated trades.
- Ensure 100% deterministic decision making.

### Policy: 2.3B-CONSERVATIVE

| Constraint | Value | Action |
| --- | --- | --- |
| `max_position_size` | $1000.00 | BLOCK if exceeded |
| `max_daily_loss` | $500.00 | BLOCK if exceeded |
| `max_total_exposure` | $5000.00 | BLOCK if exceeded |
| `max_asset_exposure` | $2000.00 | BLOCK if exceeded |
| `emergency_stop` | `false` | BLOCK if `true` |
| `capital_enabled` | `false` | BLOCK (Global Guard) |

### Exposure Model Scoring

| Risk Score | Exposure State | Capital Decision |
| --- | --- | --- |
| 0 - 20 | LOW | ALLOW |
| 20 - 50 | MEDIUM | ALLOW |
| 50 - 80 | HIGH | LIMIT |
| > 80 | REJECT | BLOCK |

*Note: Position Ratio > 0.5 also triggers REJECT.*
