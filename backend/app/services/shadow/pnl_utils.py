from decimal import Decimal

def compute_shadow_pnl(
    entry_price: Decimal,
    exit_price: Decimal,
    size_usd: Decimal
) -> Decimal:
    """
    Canonical PnL formula for shadow positions.

    CONTRACT:
    - Input Domain: Decimal (high precision)
    - Input Constraints:
        - entry_price > 0 (Strict positive required for quantity scaling)
        - size_usd > 0 (Strict positive required for valid position)
    - Error Handling:
        - returns Decimal("0") if entry_price <= 0 (Division guard)
        - returns Decimal("0") if size_usd <= 0 (Zero value guard)
    - Formula:
        - quantity = size_usd / entry_price
        - pnl = (exit_price - entry_price) * quantity
    - Precision: Preserves input Decimal scale
    - Guarantees:
        - Deterministic: Same inputs always yield same PnL
        - Idempotent: Repeated calls with same inputs yield same result
        - Unit-safe: size_usd is interpreted as USD investment, not token quantity
    """
    if entry_price <= 0 or size_usd <= 0:
        return Decimal("0")

    # size is USD not quantity
    quantity = size_usd / entry_price
    return (exit_price - entry_price) * quantity
