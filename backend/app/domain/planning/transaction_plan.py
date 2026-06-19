from datetime import datetime
from pydantic import BaseModel
from app.domain.planning.quote import Quote
from app.domain.planning.route import Route
from app.domain.planning.execution_constraints import ExecutionConstraints
from app.domain.planning.transaction_instruction import TransactionInstruction


class TransactionPlan(BaseModel):
    quote: Quote
    route: Route
    constraints: ExecutionConstraints
    instructions: list[TransactionInstruction] = []
    estimated_fees: int | None = None
    slippage_bps: int | None = None
    execution_deadline: datetime | None = None
    serialized_payload: dict | None = None
    metadata: dict | None = None
