# SHADOW_EVIDENCE_PROVENANCE

## Requirement: Real Evidence Origin

All promotion snapshots must provide verifiable provenance back to individual shadow decisions.

### Metadata Requirements
For every Promotion Snapshot:
- **snapshot_hash**: SHA-256 fingerprint of all included metrics.
- **source_tables**: List of database tables contributing to the snapshot (e.g., `shadow_decision_log`).
- **decision_ids**: Complete list of UUIDs of resolved decisions included in the metrics.
- **resolution_range**: Tuple of (min_timestamp, max_timestamp) for all included decisions.
- **origin_classification**: Strict classification of the underlying data.

### Allowed Origins
- **shadow**: Data originated from real-time shadow observation of strategies.
- **synthetic**: Data generated for infrastructure or pipeline validation.
- **mixed**: A combination of shadow and synthetic data.

### Promotion Readiness Rules
A strategy is only eligible for **READY** status if:
1. `origin == shadow`
2. `mixed == reject` (Status set to `EVALUATING` or `INSUFFICIENT_VOLUME`)
3. `synthetic == reject` (Status set to `EVALUATING` or `INSUFFICIENT_VOLUME`)

### Verification
Any stakeholder must be able to reconstruct the snapshot metrics by querying the `source_tables` using the provided `decision_ids`.
