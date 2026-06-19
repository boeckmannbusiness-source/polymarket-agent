from decimal import Decimal


def compute_shadow_pnl(
    entry_price: Decimal,
    exit_price: Decimal,
    size_usd: Decimal,
    fee_pct: Decimal | None = None,
) -> Decimal:
    """
    Canonical PnL formula for shadow positions.

    quantity = size_usd / entry_price
    gross_pnl = (exit_price - entry_price) * quantity
    net_pnl = gross_pnl - entry_fee - exit_fee  (if fee_pct is given)

    Returns gross PnL when fee_pct is None, net PnL when fee_pct is provided.
    Returns Decimal("0") if entry_price <= 0 or size_usd <= 0.
    """
    if entry_price <= 0 or size_usd <= 0:
        return Decimal("0")

    quantity = size_usd / entry_price
    gross = (exit_price - entry_price) * quantity
    if fee_pct is not None and fee_pct > 0:
        fee = size_usd * fee_pct
        return gross - fee - fee  # entry_fee + exit_fee
    return gross


def compute_shadow_pnl_float(
    entry_price: float,
    exit_price: float,
    size_usd: float,
    fee_pct: float | None = None,
) -> tuple[float, float]:
    """
    Float convenience wrapper around compute_shadow_pnl.

    Returns (gross_pnl, net_pnl) where net_pnl = gross_pnl when fee_pct is None.
    """
    entry = Decimal(str(entry_price))
    exit_ = Decimal(str(exit_price))
    size = Decimal(str(size_usd))
    fee = Decimal(str(fee_pct)) if fee_pct is not None else None
    gross = compute_shadow_pnl(entry, exit_, size, fee_pct=None)
    net = compute_shadow_pnl(entry, exit_, size, fee_pct=fee) if fee_pct is not None else gross
    return float(gross), float(net)
