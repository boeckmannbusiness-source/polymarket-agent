from datetime import datetime, timezone, timedelta

from app.domain.planning.quote import Quote
from app.domain.planning.route import Route
from app.domain.planning.transaction_plan import TransactionPlan
from app.domain.planning.execution_constraints import ExecutionConstraints
from app.services.planning.transaction_builder.base_transaction_builder import TransactionBuilder
from app.services.planning.transaction_builder.instruction_builder import InstructionBuilder


DEFAULT_DEADLINE_SECONDS = 120


class JupiterTransactionBuilder(TransactionBuilder):
    """Transaction builder for Jupiter-compatible venues.

    SIMULATION ONLY — no signing, no serialization to Solana format.
    Produces a fully populated TransactionPlan with deterministic instructions.
    """

    def __init__(self, instruction_builder: InstructionBuilder | None = None):
        self._instruction_builder = instruction_builder or InstructionBuilder()

    async def build(
        self,
        quote: Quote,
        route: Route,
        constraints: ExecutionConstraints | None = None,
    ) -> TransactionPlan:
        resolved = constraints or ExecutionConstraints(max_slippage_bps=100)
        instructions = self._instruction_builder.build_instructions(quote, route)
        fees = self._instruction_builder.estimate_total_fees(instructions)
        slippage = resolved.max_slippage_bps
        deadline = datetime.now(timezone.utc) + timedelta(seconds=DEFAULT_DEADLINE_SECONDS)

        return TransactionPlan(
            quote=quote,
            route=route,
            constraints=resolved,
            instructions=instructions,
            estimated_fees=fees,
            slippage_bps=slippage,
            execution_deadline=deadline,
            serialized_payload=None,
            metadata={
                "builder": "jupiter_simulation",
                "instruction_count": len(instructions),
                "side": "buy",
            },
        )
