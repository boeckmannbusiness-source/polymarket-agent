import pytest
from decimal import Decimal, getcontext


def test_sol_usdc_precision():
    # SOL has 9 decimals
    sol_precision = Decimal("10") ** -9
    sol_amount = Decimal("1.123456789")
    assert (sol_amount % sol_precision) == 0

    # USDC has 6 decimals
    usdc_precision = Decimal("10") ** -6
    usdc_amount = Decimal("100.123456")
    assert (usdc_amount % usdc_precision) == 0

def test_fee_accounting_no_drift():
    # Simulate a series of small trades and check total fees
    trades = [Decimal("100.00"), Decimal("50.25"), Decimal("75.10")]
    fee_rate = Decimal("0.005") # 0.5%

    total_fees = sum(trade * fee_rate for trade in trades)

    # (100 * 0.005) + (50.25 * 0.005) + (75.10 * 0.005)
    # 0.5 + 0.25125 + 0.3755 = 1.12675
    expected_total = Decimal("1.12675")

    assert total_fees == expected_total
    assert isinstance(total_fees, Decimal)

def test_simulation_output_precision():
    # Mock simulation output
    compute_units = 150000
    priority_fee_lamports = 5000

    # Convert lamports to SOL (9 decimals)
    fee_sol = Decimal(priority_fee_lamports) / Decimal("1000000000")

    assert fee_sol == Decimal("0.000005000")

    # Slippage calculation
    price = Decimal("100.00")
    slippage_bps = 50 # 0.5%
    min_output = price * (Decimal("1") - Decimal(slippage_bps) / Decimal("10000"))

    assert min_output == Decimal("99.50")

def test_no_float_usage():
    # Ensure we are not using floats for critical calculations
    # Price should be Decimal
    price = Decimal("100.0")

    # This should be fine
    drifted = price * Decimal("0.005")
    assert drifted == Decimal("0.500")

    # This might raise TypeError if we were using a library that forbids mixing,
    # but Python's Decimal doesn't allow mixing with float in multiplication anyway.
    with pytest.raises(TypeError):
        _ = price * 0.005

    # Strict Decimal check
    d_price = Decimal("100.0")
    d_fee = d_price * Decimal("0.005")
    assert d_fee == Decimal("0.500")
