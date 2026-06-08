import uuid
from datetime import datetime, timezone

from app.schemas.audit_v3 import (
    MicroCapitalAuditReport, MicroCapitalReadinessReport,
)
from app.services.audit_v3.execution_safety_audit import execution_safety_audit
from app.services.audit_v3.capital_protection_audit import capital_protection_audit
from app.services.audit_v3.fail_closed_audit import fail_closed_audit
from app.services.audit_v3.runtime_enforcement_audit import runtime_enforcement_audit
from app.services.audit_v3.operational_readiness_audit import operational_readiness_audit
from app.services.audit.audit_logger import emit as audit_emit
from app.core.metrics import (
    audit_v3_runs_total, audit_v3_execution_score, audit_v3_capital_score,
    audit_v3_fail_closed_score, audit_v3_runtime_score, audit_v3_operational_score,
    audit_v3_gate_score,
)


class MicroCapitalReadinessPipeline:
    def __init__(self):
        self._latest: MicroCapitalAuditReport | None = None

    async def run(self) -> MicroCapitalAuditReport:
        audit_id = f"audit-v3-{str(uuid.uuid4())[:8]}"
        await audit_emit("v3.audit.started", "audit_v3", audit_id, {})

        # Step 1: Execution Safety
        execution_safety = await execution_safety_audit.audit()

        # Step 2: Capital Protection
        capital_protection = await capital_protection_audit.audit()

        # Step 3: Fail-Closed
        fail_closed = await fail_closed_audit.audit()

        # Step 4: Runtime Enforcement
        runtime_enforcement = await runtime_enforcement_audit.audit()

        # Step 5: Operational Readiness
        operational_readiness = await operational_readiness_audit.audit()

        # Step 6: Micro-Capital Readiness Gate
        readiness = self._evaluate_readiness(
            execution_safety.score,
            capital_protection.score,
            fail_closed.score,
            runtime_enforcement.score,
            operational_readiness.overall_score,
        )

        report = MicroCapitalAuditReport(
            audit_id=audit_id,
            executed_at=datetime.now(timezone.utc).isoformat(),
            execution_safety=execution_safety,
            capital_protection=capital_protection,
            fail_closed=fail_closed,
            runtime_enforcement=runtime_enforcement,
            operational_readiness=operational_readiness,
            micro_capital_readiness=readiness,
            pipeline_status="completed",
        )

        self._latest = report

        # Update metrics
        audit_v3_runs_total.inc()
        audit_v3_execution_score.set(execution_safety.score)
        audit_v3_capital_score.set(capital_protection.score)
        audit_v3_fail_closed_score.set(fail_closed.score)
        audit_v3_runtime_score.set(runtime_enforcement.score)
        audit_v3_operational_score.set(operational_readiness.overall_score)
        audit_v3_gate_score.set(readiness.overall_score)

        # Emit audit events
        await audit_emit("v3.audit.completed", "audit_v3", audit_id, {
            "classification": readiness.classification,
            "overall_score": readiness.overall_score,
            "execution_safety": execution_safety.score,
            "capital_protection": capital_protection.score,
            "fail_closed": fail_closed.score,
            "runtime_enforcement": runtime_enforcement.score,
            "operational_readiness": operational_readiness.overall_score,
        })
        await audit_emit("v3.gate.evaluated", "audit_v3", audit_id, {
            "classification": readiness.classification,
            "overall_score": readiness.overall_score,
        })

        return report

    def _evaluate_readiness(
        self,
        execution_safety: float,
        capital_protection: float,
        fail_closed: float,
        runtime_enforcement: float,
        operational_readiness: float,
    ) -> MicroCapitalReadinessReport:
        overall = round(
            (execution_safety + capital_protection + fail_closed +
             runtime_enforcement + operational_readiness) / 5, 1
        )

        classification = self._classify(
            execution_safety, fail_closed, capital_protection,
            runtime_enforcement, operational_readiness,
        )
        risk_summary = self._build_risk_summary(
            execution_safety, capital_protection, fail_closed,
            runtime_enforcement, operational_readiness,
        )
        recommendation = self._build_recommendation(classification, overall)

        return MicroCapitalReadinessReport(
            execution_safety_score=execution_safety,
            capital_protection_score=capital_protection,
            fail_closed_score=fail_closed,
            runtime_enforcement_score=runtime_enforcement,
            operational_readiness_score=operational_readiness,
            overall_score=overall,
            classification=classification,
            recommendation=recommendation,
            risk_summary=risk_summary,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def _classify(
        self,
        execution_safety: float,
        fail_closed: float,
        capital_protection: float,
        runtime_enforcement: float,
        operational_readiness: float,
    ) -> str:
        if execution_safety < 70 or fail_closed < 70:
            return "NOT_READY"
        all_above_70 = (
            execution_safety >= 70 and capital_protection >= 70
            and fail_closed >= 70 and runtime_enforcement >= 70
            and operational_readiness >= 70
        )
        if not all_above_70:
            return "NOT_READY"
        all_above_85 = (
            execution_safety >= 85 and capital_protection >= 85
            and fail_closed >= 85 and runtime_enforcement >= 85
            and operational_readiness >= 85
        )
        if all_above_85 and fail_closed == 100:
            return "MICRO_CAPITAL_READY"
        return "PAPER_READY"

    def _build_risk_summary(
        self,
        execution_safety: float,
        capital_protection: float,
        fail_closed: float,
        runtime_enforcement: float,
        operational_readiness: float,
    ) -> str:
        parts: list[str] = []
        if execution_safety < 70:
            parts.append(f"Execution safety is {execution_safety:.0f}/100")
        if capital_protection < 70:
            parts.append(f"Capital protection is {capital_protection:.0f}/100")
        if fail_closed < 70:
            parts.append(f"Fail-closed is {fail_closed:.0f}/100")
        if runtime_enforcement < 70:
            parts.append(f"Runtime enforcement is {runtime_enforcement:.0f}/100")
        if operational_readiness < 70:
            parts.append(f"Operational readiness is {operational_readiness:.0f}/100")
        if not parts:
            parts.append("All dimensions meet minimum thresholds for micro-capital deployment")
        return "; ".join(parts)

    def _build_recommendation(self, classification: str, overall: float) -> str:
        if classification == "MICRO_CAPITAL_READY":
            return (
                f"System scores {overall}/100 — SAFE FOR 25-100€ LIVE TEST. "
                f"All runtime safety gates pass; fail-closed verified at 100%; "
                f"execution paths fully gated."
            )
        elif classification == "PAPER_READY":
            return (
                f"System scores {overall}/100 — NOT SAFE for live capital yet. "
                f"Paper trading only until all dimensions exceed 85 "
                f"and fail-closed reaches 100."
            )
        else:
            return (
                f"System scores {overall}/100 — NOT READY. "
                f"Critical safety gaps detected: execution_safety >= 70 "
                f"and fail_closed >= 70 required."
            )

    async def get_latest(self) -> MicroCapitalAuditReport | None:
        return self._latest


micro_capital_readiness_pipeline = MicroCapitalReadinessPipeline()
