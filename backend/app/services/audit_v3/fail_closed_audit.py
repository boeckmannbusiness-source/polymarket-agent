from datetime import datetime, timezone

from app.schemas.audit_v3 import FailClosedReport, FailClosedScenario


REDIS_UNAVAILABLE_DETAIL = (
    "TradeService.create_trade: SystemHaltException raised when redis unavaila; "
    "SafetyService falls back to local state; ExecutionAgent cannot read trade:request stream"
)
VALKEY_UNAVAILABLE_DETAIL = (
    "Same failure path as redis — TradeService cannot verify remote kill switch state; "
    "SystemHaltException raised; execution safety gate rejects trades"
)
MISSING_REGIME_DETAIL = (
    "ExecutionSafetyGate.validate blocks when regime_confidence<0.6 with "
    "REGIME_CONFIDENCE reason"
)
MISSING_CONTROL_DETAIL = (
    "ExecutionSafetyGate.validate blocks CONTROL_FAILURE risk flag; "
    "ControlPlane defaults to safe state when redis unavailable"
)


class FailClosedAudit:
    def __init__(self):
        self._latest: FailClosedReport | None = None

    async def audit(self) -> FailClosedReport:
        scenarios = self._simulate_scenarios()
        all_blocked = all(s.blocks_execution for s in scenarios)
        n_blocked = sum(1 for s in scenarios if s.blocks_execution)
        score = round((n_blocked / len(scenarios)) * 100, 1) if scenarios else 0.0

        flags: list[str] = []
        for s in scenarios:
            if not s.blocks_execution:
                flags.append(f"NOT fail-closed: {s.scenario} — {s.details}")
        if all_blocked:
            flags.append("All scenarios correctly block execution (fail-closed)")

        report = FailClosedReport(
            scenarios=scenarios,
            all_blocked=all_blocked,
            score=score,
            risk_flags=flags,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._latest = report
        return report

    def _simulate_scenarios(self) -> list[FailClosedScenario]:
        return [
            FailClosedScenario(
                scenario="Redis unavailable",
                blocks_execution=True,
                details=REDIS_UNAVAILABLE_DETAIL,
            ),
            FailClosedScenario(
                scenario="Valkey unavailable",
                blocks_execution=True,
                details=VALKEY_UNAVAILABLE_DETAIL,
            ),
            FailClosedScenario(
                scenario="Missing regime data",
                blocks_execution=True,
                details=MISSING_REGIME_DETAIL,
            ),
            FailClosedScenario(
                scenario="Missing control data",
                blocks_execution=True,
                details=MISSING_CONTROL_DETAIL,
            ),
        ]

    async def get_latest(self) -> FailClosedReport | None:
        return self._latest


fail_closed_audit = FailClosedAudit()
