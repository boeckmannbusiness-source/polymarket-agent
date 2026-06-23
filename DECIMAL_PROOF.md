# Decimal Proof

## Precision Standards
- SOL: 9 decimals
- USDC: 6 decimals
- Internal Accounting: `Decimal` only

## Results
`test_decimal_precision.py` confirms:
- No precision drift in fee calculations.
- Accurate lamport-to-SOL conversions.
- Strict rejection of `float` in critical operations.
- 100% deterministic arithmetic for PnL tracking.
