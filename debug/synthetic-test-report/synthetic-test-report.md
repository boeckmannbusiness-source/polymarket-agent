# Synthetic Market Shock Test Report

- **Date**: 2026-05-29T16:24:00.674591+00:00
- **Seed**: 42
- **Total Duration**: 72.8s

### Overall Summary

| Metric | Value |
|--------|-------|
| Scenarios Run | 1 |
| All Passed | [PASS] |
| Total Events Injected | 16 |
| Total Signals Generated | 224 |
| Total Trades Executed | 6 |
| Total Crashes | 0 |

### Scenario Summary

| Scenario | Events | Signals | Trades | Wins/Losses | Crashes | Passed |
|----------|--------|---------|--------|-------------|---------|--------|
| Whale Buy Cascade | 16 | 224 | 6 | 0/0 | 0 | [PASS] |

## Scenario: Whale Buy Cascade

- **Description**: Sequential BUY trades with increasing sizes and rising prices
- **Events Injected**: 16
- **Status**: [PASS]

### Pipeline Results

| Metric | Value |
|--------|-------|
| Signals Generated | 224 |
| Signals Rejected | 0 |
| Trades Executed | 6 |
| Trades Closed | 0 |
| Win/Loss | 0/0 |
| Avg PnL | $0.0000 |
| Max Drawdown | 0.00% |
| Guardian Disables | 0 |
| Crashes | 0 |

### Strategy Activation

| Strategy | Signals |
|----------|---------|
| ensemble | 157 |
| whale_following | 62 |
| momentum | 5 |

### Risk Overlay Activations

- Overlay state: `ACTIVE`

### Execution Details

| Trade | Market | Side | Outcome | Size | Price | PnL | Status | Reason |
|-------|--------|------|---------|------|-------|-----|--------|--------|
| c52b74e0 | cbed0fc2 | buy | YES | 2885.33 | 0 | 0 | open | Auto-execution signal=62889c7c-9be9-40fb-ab04-e2780cd0140b strategy=ensemble confidence=0.5933 |
| e5073cf8 | f2280643 | buy | YES | 3367.94002968 | 0.15263719 | 0 | cancelled | N/A |
| 2e5fd1c3 | 82aa8352 | buy | YES | 492.13321054 | 0.81421141 | 0 | cancelled | N/A |
| 046109a9 | 48765b18 | buy | YES | 1311.31794954 | 0.63785425 | 0 | cancelled | N/A |
| dbb23eab | aa29a929 | buy | YES | 3882.66968635 | 0.53234435 | 0 | cancelled | N/A |
| 3da815ce | 0f3442df | buy | YES | 1740.39251028 | 0.79585568 | 0 | cancelled | N/A |

### Determinism

- **Hash**: `0d4d449a95706b9e228b67e9018db279baa23d01112aaeedad7eba60becd500d`
- **Replay Drift**: 0.00%

---

## Final Verdict

### [PASS] ALL SCENARIOS PASSED

The system demonstrates rational behavior under synthetic market stress. Pipeline integrity is confirmed. Proceeding to the next phase is recommended.