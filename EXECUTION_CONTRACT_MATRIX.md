# EXECUTION_CONTRACT_MATRIX.md

| Component | Input | Output | Outcome Dependency | Venue Neutral | Simulation Compatible | Replay Compatible | Backward Compat |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `BaseExchangeAdapter` | `Intent \| Order` | `Result` | None | Yes | Yes | Yes | Yes |
| `ExecutionResult` | N/A | N/A | None | Yes | Yes | Yes | Yes |
| `ExecutionIntent` | N/A | N/A | None | Yes | Yes | Yes | Yes (compat_*) |
| `ExecutionService` | `Signal \| Trade` | `Result` | None | Yes | Yes | Yes | Yes |
| `SolanaSimulationAdapter` | `Plan` | `Result` | None | No (Solana) | Yes | Yes | N/A |
| `SolanaTransactionBuilder` | `Plan` | `Envelope` | None | No (Solana) | Yes | Yes | N/A |

### Verification Audit
- **No outcome dependency**: Verified in `ExecutionResult`, `ExecutionIntent`, and `ExecutionTrace`.
- **Venue-neutral result**: `ExecutionResult` uses generic fields (`quantity_executed`, `average_price`).
- **Simulation compatible**: `SolanaSimulationAdapter` implements the building and simulation flow.
- **Replay compatible**: `TransactionPlan` encapsulates quotes; `SolanaTransactionBuilder` uses plan data.
- **Backward compatibility**: `ExecutionIntent` includes `compat_` fields for legacy tests.
