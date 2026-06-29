# REPORT_INTEGRITY_VALIDATOR

## Validation Rules

All shadow intelligence reports must pass the following integrity checks before rendering.

### 1. Status Consistency
- **Rule**: If `status == READY`, then `origin` MUST be `shadow`.
- **Invariants**:
  - `READY` + `synthetic` = FAIL
  - `READY` + `mixed` = FAIL

### 2. Origin Consistency
- **Rule**: `origin` MUST be one of: `shadow`, `synthetic`, `mixed`.
- **Rule**: If `decision_ids` is empty, `origin` MUST be `synthetic`.

### 3. Population Consistency
- **Rule**: `Total Decisions` == `OPEN` + `CLOSED` + `RESOLVED`.
- **Rule**: `resolved_count` in snapshot MUST match the number of items in `decision_ids`.

### 4. Percentage Consistency
- **Rule**: Sum of bucket percentages (EXACT, NUMERIC_DRIFT, TIMING_DRIFT, UNKNOWN) MUST be 100% (within floating point tolerance).
- **Rule**: If `total == 0`, percentages MUST be `NOT_AVAILABLE`.

### 5. Snapshot Consistency
- **Rule**: `snapshot_hash` MUST match the SHA-256 hash of the snapshot metrics.
- **Rule**: Resolution range MUST encompass all resolution timestamps of `decision_ids`.

## Enforcement
The `ReportIntegrityValidator` component executes these checks during report generation. Any violation raises a `ReportIntegrityError` and aborts rendering.
