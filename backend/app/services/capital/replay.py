from app.domain.replay.execution_trace import ExecutionTrace


class CapitalReplay:
    """
    Validates risk decisions during replay.
    MUST NOT recompute exposure, refresh balances, or call RPC.
    """
    def validate(self, trace: ExecutionTrace) -> bool:
        if not trace.risk:
            # If no risk receipt, it might be an old trace or failed before risk check
            return True

        # 1. Restore decision (implicit in trace.risk)
        # 2. Validate hash
        return trace.risk.verify()
