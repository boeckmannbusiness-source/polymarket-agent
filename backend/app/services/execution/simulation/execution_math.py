from decimal import Decimal
from typing import Sequence

from app.domain.execution import FillInfo
from app.domain.planning.transaction_instruction import TransactionInstruction


def compute_slippage_price(base_price: Decimal, slippage_bps: int) -> Decimal:
    if base_price == Decimal("0"):
        return Decimal("0")
    slippage_decimal = Decimal(str(slippage_bps)) / Decimal("10000")
    return base_price * (Decimal("1") + slippage_decimal)


def compute_fee(amount: Decimal, fee_bps: int = 10) -> Decimal:
    return amount * Decimal(str(fee_bps)) / Decimal("10000")


def compute_route_cost(route_type: str, hops: list[str], amount: Decimal) -> Decimal:
    base_cost = amount * Decimal("0.0005")
    if route_type == "SPLIT":
        return base_cost * Decimal(str(len(hops))) * Decimal("2")
    return base_cost * Decimal(str(len(hops)))


def aggregate_fees(fees: list[Decimal]) -> Decimal:
    return sum(fees, Decimal("0"))


def compute_average_price(fills: Sequence[FillInfo]) -> Decimal:
    if not fills:
        return Decimal("0")
    total_value = sum(f.size * f.price for f in fills)
    total_size = sum(f.size for f in fills)
    return total_value / total_size if total_size else Decimal("0")


def compute_estimated_latency_ms(instructions: list[TransactionInstruction], base_ms: float = 100.0, per_instruction_ms: float = 50.0) -> float:
    return base_ms + len(instructions) * per_instruction_ms
