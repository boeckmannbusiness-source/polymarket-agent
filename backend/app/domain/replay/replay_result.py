from decimal import Decimal
from pydantic import BaseModel

from app.domain.execution import ExecutionResult
from app.domain.replay.execution_trace import ExecutionTrace


class ReplayResult(BaseModel):
    trace: ExecutionTrace
    original_result: ExecutionResult
    replay_result: ExecutionResult
    match: bool
    fingerprint_original: str
    fingerprint_replay: str
