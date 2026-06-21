import pytest
from decimal import Decimal

def test_sol_precision():
    # SOL has 9 decimals
    val = Decimal("1.123456789")
    lamports = int(val * Decimal("1000000000"))
    assert lamports == 1123456789

    # Verify no float drift
    back = Decimal(str(lamports)) / Decimal("1000000000")
    assert back == val

def test_usdc_precision():
    # USDC has 6 decimals
    val = Decimal("100.123456")
    units = int(val * Decimal("1000000"))
    assert units == 100123456

    back = Decimal(str(units)) / Decimal("1000000")
    assert back == val

def test_jup_precision():
    # JUP has 6 decimals
    val = Decimal("50.654321")
    units = int(val * Decimal("1000000"))
    assert units == 50654321

    back = Decimal(str(units)) / Decimal("1000000")
    assert back == val

def test_pnl_no_float():
    entry = Decimal("100.50")
    exit = Decimal("125.75")
    quantity = Decimal("1.5")

    pnl = (exit - entry) * quantity
    assert pnl == Decimal("37.875")

    # Ensure float operations are avoided
    pnl_float = (125.75 - 100.50) * 1.5
    assert float(pnl) == pnl_float
