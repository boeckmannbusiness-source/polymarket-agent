from decimal import Decimal

from app.domain.execution import ExecutionResult
from app.domain.replay.execution_trace import ExecutionTrace
from app.domain.replay.replay_result import ReplayResult
from app.services.replay.execution_fingerprint import ExecutionFingerprint
from app.services.replay.replay_engine import ReplayEngine


class ReplayValidator:
    def __init__(self, engine: ReplayEngine | None = None):
        self._engine = engine or ReplayEngine()

    def validate(self, trace: ExecutionTrace, original: ExecutionResult) -> ReplayResult:
        replay_result = self._engine.replay(trace)

        fp_original = ExecutionFingerprint.generate(trace.intent, trace.plan, original, trace.seed)
        fp_replay = ExecutionFingerprint.generate(trace.intent, trace.plan, replay_result, trace.seed)

        match = self._results_match(original, replay_result)

        return ReplayResult(
            trace=trace,
            original_result=original,
            replay_result=replay_result,
            match=match,
            fingerprint_original=fp_original,
            fingerprint_replay=fp_replay,
        )

    @staticmethod
    def _results_match(a: ExecutionResult, b: ExecutionResult) -> bool:
        if a.status != b.status:
            return False
        if a.quantity_executed != b.quantity_executed:
            return False
        if a.average_price != b.average_price:
            return False
        if len((a.fills or [])) != len((b.fills or [])):
            return False
        for fa, fb in zip(a.fills or [], b.fills or []):
            if fa.size != fb.size:
                return False
            if fa.price != fb.price:
                return False
        return True
