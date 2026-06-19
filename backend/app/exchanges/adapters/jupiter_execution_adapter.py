from app.exchanges.base import BaseExchangeAdapter
from app.exchanges.adapters.base_execution_adapter import BaseExecutionAdapter
from app.domain.execution import ExecutionIntent, ExecutionResult
from app.domain.planning.transaction_plan import TransactionPlan
from app.services.execution.simulation import ExecutionSimulator


class JupiterExecutionAdapter(BaseExchangeAdapter, BaseExecutionAdapter):
    """Jupiter-compatible execution adapter.

    SIMULATION ONLY — no swaps, no blockchain interaction.
    Consumes TransactionPlan and returns deterministic ExecutionResult.
    """

    def __init__(self, db=None, simulator: ExecutionSimulator | None = None):
        self.db = db
        self._simulator = simulator or ExecutionSimulator()

    # ── BaseExecutionAdapter interface ─────────────────────────

    async def execute(self, plan: TransactionPlan) -> ExecutionResult:
        return await self._simulator.simulate(plan, adapter_name="jupiter_simulated")

    async def health_check(self) -> dict:
        return {"status": "simulated", "adapter": "jupiter_simulated"}

    async def get_supported_assets(self) -> list[str]:
        return ["SOL", "USDC"]

    # ── BaseExchangeAdapter interface (legacy compatibility) ────

    async def submit_order(self, intent: ExecutionIntent) -> ExecutionResult:
        if intent.transaction_plan is not None:
            return await self.execute(intent.transaction_plan)
        raise NotImplementedError(
            "JupiterExecutionAdapter requires a TransactionPlan. "
            "Use planner.plan() before submitting."
        )

    async def cancel_order(self, order_id: str) -> dict:
        return {"status": "simulated_cancelled", "order_id": order_id}

    async def get_order_status(self, order_id: str) -> dict:
        return {"status": "simulated_filled", "order_id": order_id}

    async def get_positions(self) -> list[dict]:
        return []

    async def get_balances(self) -> dict:
        return {"SOL": 0, "USDC": 0}

    async def get_fills(self, since) -> list[dict]:
        return []
