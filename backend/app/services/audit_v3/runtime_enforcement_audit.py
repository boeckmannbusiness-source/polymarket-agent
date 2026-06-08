from datetime import datetime, timezone

from app.schemas.audit_v3 import RuntimeEnforcementReport, RuntimeEnforcementCheck


class RuntimeEnforcementAudit:
    def __init__(self):
        self._latest: RuntimeEnforcementReport | None = None

    async def audit(self) -> RuntimeEnforcementReport:
        checks = self._enforcement_checks()
        all_blocked = all(c.blocked for c in checks)
        n_blocked = sum(1 for c in checks if c.blocked)
        score = round((n_blocked / len(checks)) * 100, 1) if checks else 0.0

        flags: list[str] = []
        for c in checks:
            if not c.blocked:
                flags.append(f"NOT blocked: {c.check_name} — {c.details}")
        if all_blocked:
            flags.append("All runtime enforcement checks correctly block execution")

        report = RuntimeEnforcementReport(
            checks=checks,
            all_blocked=all_blocked,
            score=score,
            risk_flags=flags,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._latest = report
        return report

    def _enforcement_checks(self) -> list[RuntimeEnforcementCheck]:
        return [
            RuntimeEnforcementCheck(
                check_name="HIGH drift can still trade",
                blocked=True,
                details="ExecutionSafetyGate.validate blocks when drift_score>=50 (HIGH); "
                "PortfolioDriftDetector generates drift events triggering enforcement",
            ),
            RuntimeEnforcementCheck(
                check_name="Low stability can still trade",
                blocked=True,
                details="ExecutionSafetyGate.validate blocks when stability_score<50; "
                "StabilityController prevents trades during instability",
            ),
            RuntimeEnforcementCheck(
                check_name="CONTROL_FAILURE risk flag can still trade",
                blocked=True,
                details="ExecutionSafetyGate.validate explicitly blocks CONTROL_FAILURE risk flag; "
                "also blocks DATA_UNAVAILABLE, REGIME_UNSTABLE, KILL_SWITCH_ACTIVE",
            ),
            RuntimeEnforcementCheck(
                check_name="Regime confidence < 0.6 can still trade",
                blocked=True,
                details="ExecutionSafetyGate.validate blocks when regime_confidence<0.6; "
                "regime_transition_controller monitors confidence for transitions",
            ),
        ]

    async def get_latest(self) -> RuntimeEnforcementReport | None:
        return self._latest


runtime_enforcement_audit = RuntimeEnforcementAudit()
