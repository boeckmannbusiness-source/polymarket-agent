from decimal import Decimal
from datetime import datetime, timezone
from uuid import uuid4

from app.domain.planning.transaction_plan import TransactionPlan
from app.domain.planning.transaction_instruction import TransactionInstruction
from app.domain.execution import FillInfo
from app.domain.replay.replay_seed import ReplaySeed


class FillSimulator:
    """Generates deterministic fills from a TransactionPlan's instructions.

    NO blockchain interaction.
    """

    @staticmethod
    def simulate_fills(
        plan: TransactionPlan,
        slippage_bps: int | None = None,
        seed: ReplaySeed | None = None,
    ) -> list[FillInfo]:
        slippage = slippage_bps if slippage_bps is not None else (plan.slippage_bps or 0)
        fills: list[FillInfo] = []

        for i, instruction in enumerate(plan.instructions):
            fill = FillSimulator._simulate_fill_for_instruction(instruction, i, slippage, plan, seed)
            fills.append(fill)

        return fills

    @staticmethod
    def _simulate_fill_for_instruction(
        instruction: TransactionInstruction,
        index: int,
        slippage_bps: int,
        plan: TransactionPlan,
        seed: ReplaySeed | None = None,
    ) -> FillInfo:
        base_price = plan.quote.estimated_price or Decimal("0")
        slippage_decimal = Decimal(str(slippage_bps)) / Decimal("10000")
        simulated_price = base_price * (Decimal("1") + slippage_decimal) if base_price else Decimal("0")
        fee = instruction.amount * Decimal("0.001")

        if seed:
            import hashlib
            import uuid
            from datetime import datetime
            h = hashlib.sha256(f"{seed.seed}_{index}".encode()).hexdigest()
            fill_id = str(uuid.UUID(h[:32]))
            timestamp = datetime.fromisoformat(seed.timestamp_bucket)
        else:
            fill_id = str(uuid4())
            from datetime import datetime, timezone
            timestamp = datetime.now(timezone.utc)

        return FillInfo(
            fill_id=fill_id,
            size=instruction.amount,
            price=simulated_price,
            fee=fee,
            timestamp=timestamp,
        )

    @staticmethod
    def compute_average_price(fills: list[FillInfo]) -> Decimal:
        if not fills:
            return Decimal("0")
        total_value = sum(f.size * f.price for f in fills)
        total_size = sum(f.size for f in fills)
        return total_value / total_size if total_size else Decimal("0")
