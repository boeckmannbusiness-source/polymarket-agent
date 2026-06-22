from app.exchanges.base import BaseExchangeAdapter
from app.exchanges.adapters.base_execution_adapter import BaseExecutionAdapter
from app.models import ExchangeOrder
from app.domain.execution import ExecutionResult
from app.domain.planning.transaction_plan import TransactionPlan
from app.services.execution.simulation import ExecutionSimulator
from app.domain.replay.replay_seed import ReplaySeed


class JupiterExecutionAdapter(BaseExchangeAdapter, BaseExecutionAdapter):
    def __init__(self, db=None, simulator: ExecutionSimulator | None = None):
        self.db = db
        self._simulator = simulator or ExecutionSimulator()

    async def execute(self, plan: TransactionPlan, seed: ReplaySeed | None = None) -> ExecutionResult:
        return await self._simulator.simulate(plan, adapter_name="jupiter_simulated", seed=seed)

    async def health_check(self) -> dict:
        return {"status": "simulated", "adapter": "jupiter_simulated"}

    async def get_supported_assets(self) -> list[str]:
        return ["SOL", "USDC"]

    async def submit_order(self, order: ExchangeOrder) -> ExecutionResult:
        if not order.raw_request or "plan" not in order.raw_request or not order.raw_request["plan"]:
             raise ValueError("JupiterExecutionAdapter requires a TransactionPlan in order.raw_request['plan'].")
        plan_data = order.raw_request["plan"]
        plan = TransactionPlan(**plan_data)
        seed = None
        intent_data = order.raw_request.get("intent")
        if intent_data and "metadata" in intent_data and intent_data["metadata"]:
            seed_data = intent_data["metadata"].get("seed")
            if seed_data:
                if isinstance(seed_data, dict): seed = ReplaySeed(**seed_data)
                elif isinstance(seed_data, ReplaySeed): seed = seed_data
        return await self.execute(plan, seed=seed)

    async def cancel_order(self, order_id: str) -> dict:
        return {"status": "simulated_cancelled", "order_id": order_id}

    async def get_order_status(self, order_id: str) -> dict:
        return {"status": "simulated_filled", "order_id": order_id}
