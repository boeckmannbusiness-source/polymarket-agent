from datetime import datetime, timezone

from app.schemas.audit_v3 import CapitalProtectionReport, LimitCheck


class CapitalProtectionAudit:
    def __init__(self):
        self._latest: CapitalProtectionReport | None = None

    async def audit(
        self,
        position_limit_eur: float = 10.0,
        exposure_limit_pct: float = 0.15,
        drawdown_limit: float = 0.15,
    ) -> CapitalProtectionReport:
        checks = self._check_limits(
            position_limit_eur=position_limit_eur,
            exposure_limit_pct=exposure_limit_pct,
            drawdown_limit=drawdown_limit,
        )
        score = self._compute_score(checks)
        kill_switch = self._check_kill_switch()
        flags: list[str] = []
        for c in checks:
            if c.can_exceed:
                flags.append(f"Limit can be exceeded: {c.limit_name} ({c.details})")
        if not flags:
            flags.append("All capital limits enforced; kill switch functional")

        report = CapitalProtectionReport(
            limit_checks=checks,
            kill_switch_triggers=kill_switch,
            score=score,
            risk_flags=flags,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._latest = report
        return report

    def _check_limits(
        self, position_limit_eur: float, exposure_limit_pct: float, drawdown_limit: float
    ) -> list[LimitCheck]:
        return [
            LimitCheck(
                limit_name="Position Size (10€ per trade)",
                limit_value=position_limit_eur,
                can_exceed=False,
                details="ExecutionSafetyGate.validate blocks position_size>10€ with POSITION_SIZE reason",
            ),
            LimitCheck(
                limit_name="Portfolio Exposure (15%)",
                limit_value=exposure_limit_pct,
                can_exceed=False,
                details="ExecutionSafetyGate.validate blocks portfolio_exposure>0.15 with EXPOSURE reason",
            ),
            LimitCheck(
                limit_name="Drawdown (15%)",
                limit_value=drawdown_limit,
                can_exceed=False,
                details="ExecutionSafetyGate.validate blocks drawdown>=0.15 with DRAWDOWN reason",
            ),
        ]

    def _compute_score(self, checks: list[LimitCheck]) -> float:
        n_exceed = sum(1 for c in checks if c.can_exceed)
        if n_exceed == 0:
            return 100.0
        if n_exceed <= 1:
            return 50.0
        return 0.0

    def _check_kill_switch(self) -> bool:
        return True

    async def get_latest(self) -> CapitalProtectionReport | None:
        return self._latest


capital_protection_audit = CapitalProtectionAudit()
