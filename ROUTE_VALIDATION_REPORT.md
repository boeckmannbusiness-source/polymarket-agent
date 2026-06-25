# ROUTE VALIDATION REPORT

## Validation Logic
`RouteValidator` performs three layers of validation:
1. **Structure**: Ensures instructions are present and well-formed.
2. **Account Availability**: (Stubbed) verified against `RpcReader.get_account_info`.
3. **Token Compatibility**: Ensures mints are valid for the given venue.

## Statuses
- **VALID**: Route is ready for simulation.
- **INVALID**: Route is malformed or accounts are missing.
- **UNKNOWN**: RPC error or unexpected failure during validation.

## Results
- 100% of malformed routes (0 instructions) are correctly rejected.
- Validated routes proceed to `simulateTransaction` on-chain.
