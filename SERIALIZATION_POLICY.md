# SERIALIZATION POLICY

## Canonical JSON
The system uses a recursive canonical serialization method for all hash inputs:
1. **Keys**: All dictionary keys are sorted alphabetically.
2. **Decimals**: All `Decimal` values are normalized (trailing zeros removed) and serialized in fixed-point notation (`:f`).
3. **Lists**: List order is preserved; nested objects are recursively serialized.
4. **Encoding**: Final JSON string is encoded to `UTF-8`.

## Account State Hashing
To ensure stability regardless of RPC implementation details:
1. RPC account results are sorted by their string representation (pubkey/data) before hashing.
2. The resulting list is serialized to JSON and hashed with SHA-256.

## Forbidden Patterns
- No use of `dict` iteration order.
- No inclusion of raw `datetime` objects (must be ISO-8601 strings).
- No floating-point types in hash components.
- No runtime-dependent identifiers.
