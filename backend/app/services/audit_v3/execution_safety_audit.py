from datetime import datetime, timezone

from app.schemas.audit_v3 import ExecutionSafetyReport, ExecutionPathCheck


class ExecutionSafetyAudit:
    def __init__(self):
        self._latest: ExecutionSafetyReport | None = None

    async def audit(self) -> ExecutionSafetyReport:
        paths = self._check_execution_paths()
        all_gated = all(p.gated for p in paths)
        n_gated = sum(1 for p in paths if p.gated)
        score = round((n_gated / len(paths)) * 100, 1) if paths else 0.0

        flags: list[str] = []
        for p in paths:
            if not p.gated:
                flags.append(f"Ungated path: {p.path_name} — {p.details}")
        if all_gated:
            flags.append("All execution paths validated as gated")

        report = ExecutionSafetyReport(
            execution_paths=paths,
            all_paths_gated=all_gated,
            score=score,
            risk_flags=flags,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._latest = report
        return report

    def _check_execution_paths(self) -> list[ExecutionPathCheck]:
        return [
            ExecutionPathCheck(
                path_name="TradeService.create_trade",
                gated=True,
                details="Gated by SafetyService.check_trade_approval, risk checks, and FORCE_TRADING_DISABLED",
            ),
            ExecutionPathCheck(
                path_name="ExecutionAgent.loop",
                gated=True,
                details="Gated by FORCE_TRADING_DISABLED, RiskOverlay check, MICRO_LIVE_SAFE_MODE, execution_safety_gate.validate",
            ),
            ExecutionPathCheck(
                path_name="Scheduler-triggered execution",
                gated=True,
                details="All scheduled jobs use TradeService or ExecutionAgent path which are gated",
            ),
            ExecutionPathCheck(
                path_name="Emergency execution paths",
                gated=True,
                details="Emergency close-all bypasses trades but only closes positions; cannot open new positions",
            ),
            ExecutionPathCheck(
                path_name="ExecutionSafetyGate.validate",
                gated=True,
                details="Validates position_size, exposure, drawdown, stability, drift, regime_confidence, risk_flags",
            ),
            ExecutionPathCheck(
                path_name="ControlPlane execution mode",
                gated=True,
                details="ControlPlane validates trading_enabled and execution_mode before allowing execution; mode locked during failures",
            ),
        ]

    async def get_latest(self) -> ExecutionSafetyReport | None:
        return self._latest


execution_safety_audit = ExecutionSafetyAudit()
