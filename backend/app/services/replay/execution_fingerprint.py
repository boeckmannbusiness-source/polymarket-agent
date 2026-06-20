import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal

from app.domain.execution import ExecutionResult, ExecutionIntent
from app.domain.planning.transaction_plan import TransactionPlan
from app.domain.replay.replay_seed import ReplaySeed


class ExecutionFingerprint:
    @staticmethod
    def generate(
        intent: ExecutionIntent | None,
        plan: TransactionPlan | None,
        result: ExecutionResult,
        seed: ReplaySeed | None = None,
    ) -> str:
        payload: dict = {}

        if intent:
            payload["intent"] = {
                "instrument": str(intent.instrument),
                "side": intent.side,
                "quantity": str(intent.quantity),
                "order_type": intent.order_type,
            }

        if plan:
            payload["plan"] = {
                "slippage_bps": plan.slippage_bps,
                "estimated_fees": plan.estimated_fees,
                "instruction_types": [i.instruction_type for i in plan.instructions],
                "route": {
                    "venue": plan.route.venue if plan.route else None,
                    "route_type": plan.route.route_type if plan.route else None,
                    "hops": plan.route.hops if plan.route else [],
                },
                "quote": {
                    "source": plan.quote.source if plan.quote else None,
                    "estimated_price": str(plan.quote.estimated_price) if plan.quote else None,
                }
            }

        payload["result"] = {
            "status": result.status,
            "adapter": result.adapter,
            "quantity_executed": str(result.quantity_executed) if result.quantity_executed else None,
            "average_price": str(result.average_price) if result.average_price else None,
            "fees": str(result.fees) if result.fees else None,
            "simulated_slippage": round(result.simulated_slippage, 6) if result.simulated_slippage is not None else None,
            "simulated_latency_ms": round(result.simulated_latency_ms, 2) if result.simulated_latency_ms is not None else None,
            "instruction_trace": result.instruction_trace,
            "execution_path": result.execution_path,
        }

        if result.fills:
            payload["fills"] = [
                {
                    "fill_id": f.fill_id,
                    "size": str(f.size),
                    "price": str(f.price),
                    "fee": str(f.fee) if f.fee else None,
                }
                for f in result.fills
            ]

        if seed:
            payload["seed"] = seed.model_dump()

        raw = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def generate_bucket(minutes: int = 1) -> str:
        now = datetime.now(timezone.utc)
        truncated = now.replace(second=0, microsecond=0)
        if minutes > 1:
            bucket_min = (truncated.minute // minutes) * minutes
            truncated = truncated.replace(minute=bucket_min)
        return truncated.isoformat()
