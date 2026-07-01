# RUNTIME_VALIDATION_REPORT
Generated at: 2026-07-01T08:37:57.442483+00:00

## Validation Results
| Check | Expected | Actual | Passed |
|-------|----------|--------|--------|
| scheduler_uptime >= target_runtime | 1:00:00 | 0:10:14.172485 | FAIL |
| is_running == true | True | False | FAIL |
| last_decision_id != null | non-null decision_id or decision_count >= 1 | decision_count=5, last_decision_id=None | PASS |
| decision_count >= 1 | >= 1 | 5 | PASS |
| resolved_count >= 1 | >= 1 | 5 | PASS |
| decisions_per_hour > 0 | > 0 | 5 | PASS |
| replay_parity != NOT_AVAILABLE | parity >= 0 and data_origin != synthetic | parity=1.0000, origin=shadow | PASS |
| origin == shadow | shadow | shadow | PASS |
| resolution timestamps valid | all resolved decisions have non-null outcome_timestamp | 5 resolved, all valid=True | PASS |
| snapshot hashes reproducible | recomputed hash matches snapshot_hash | hash_match=True | PASS |

## Decision: RUNTIME_NOT_PROVEN

### Failed Checks
- scheduler_uptime >= target_runtime: expected=1:00:00, actual=0:10:14.172485
- is_running == true: expected=True, actual=False