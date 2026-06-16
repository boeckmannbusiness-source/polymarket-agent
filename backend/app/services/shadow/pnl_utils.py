from decimal import Decimal

def compute_shadow_pnl(
    entry_price: Decimal,
    exit_price: Decimal,
    size_usd: Decimal
) -> Decimal:
    """
    Canonical PnL formula for shadow positions.
    size_usd is the total USD value of the position, not the quantity.
    quantity = size_usd / entry_price
    gross_pnl = (exit_price - entry_price) * quantity
    """
    if entry_price <= 0 or size_usd <= 0:
        return Decimal("0")

    # size is USD not quantity
    quantity = size_usd / entry_price
    return (exit_price - entry_price) * quantity
