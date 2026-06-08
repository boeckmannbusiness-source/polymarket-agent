import uuid
from datetime import datetime, timezone

from app.schemas.audit_v2 import SystemSafetyAuditReport
from app.services.audit_v2.system_safety_audit_service import system_safety_audit_service
from app.services.audit_v2.data_integrity_audit_service import data_integrity_audit_service
from app.services.audit_v2.feedback_cycle_check_service import feedback_cycle_check_service
from app.services.audit_v2.stress_safety_simulator import stress_safety_simulator
from app.services.audit_v2.production_gate_service import production_gate_service
from app.services.audit.audit_logger import emit as audit_emit
from app.core.metrics import (
    audit_v2_runs_total, stress_scenarios_executed_total,
    feedback_cycles_detected_total, production_gate_score,
)


class AutonomousSafetyAuditPipeline:
    def __init__(self):
        self._latest: SystemSafetyAuditReport | None = None

    async def run(
        self,
        signal_sources: dict | None = None,
        baseline_allocations: dict[str, float] | None = None,
        correlation_matrix: dict[str, dict[str, float]] | None = None,
        return_variances: dict[str, float] | None = None,
    ) -> SystemSafetyAuditReport:
        audit_id = f"audit-v2-{str(uuid.uuid4())[:8]}"
        await audit_emit("v2.audit.started", "audit_v2", audit_id, {})

        # Step 1: System Safety Audit
        system_safety = await system_safety_audit_service.audit()

        # Step 2: Data Integrity Audit
        data_integrity = await data_integrity_audit_service.audit(
            signal_sources=signal_sources,
        )

        # Step 3: Feedback Cycle Check
        feedback_cycles = await feedback_cycle_check_service.check()

        # Step 4: Stress Safety Simulation
        stress_safety = await stress_safety_simulator.simulate(
            baseline_allocations=baseline_allocations,
            correlation_matrix=correlation_matrix,
            return_variances=return_variances,
        )

        # Step 5: Production Gate Evaluation
        production_gate = await production_gate_service.evaluate(
            system_safety=system_safety,
            data_integrity=data_integrity,
            feedback_cycles=feedback_cycles,
            stress_safety=stress_safety,
        )

        report = SystemSafetyAuditReport(
            audit_id=audit_id,
            executed_at=datetime.now(timezone.utc).isoformat(),
            system_safety=system_safety,
            data_integrity=data_integrity,
            feedback_cycles=feedback_cycles,
            stress_safety=stress_safety,
            production_gate=production_gate,
            pipeline_status="completed",
        )

        self._latest = report

        # Update metrics
        audit_v2_runs_total.inc()
        for scenario in stress_safety.scenario_results:
            stress_scenarios_executed_total.labels(
                scenario_type=scenario.scenario_type
            ).inc()
        feedback_cycles_detected_total.set(len(feedback_cycles.cycles))
        production_gate_score.set(production_gate.overall_score)

        # Emit audit events
        await audit_emit("v2.audit.completed", "audit_v2", audit_id, {
            "classification": production_gate.classification,
            "overall_score": production_gate.overall_score,
            "cycles_detected": len(feedback_cycles.cycles),
            "stress_scenarios": len(stress_safety.scenario_results),
        })
        await audit_emit("v2.stress.completed", "audit_v2", audit_id, {
            "worst_case": stress_safety.worst_case_scenario,
            "overall_stress_score": stress_safety.overall_stress_score,
        })
        await audit_emit("v2.cycle.detected", "audit_v2", audit_id, {
            "cycles": len(feedback_cycles.cycles),
            "overall_risk": feedback_cycles.overall_risk_level,
        })
        await audit_emit("v2.gate.evaluated", "audit_v2", audit_id, {
            "classification": production_gate.classification,
            "overall_score": production_gate.overall_score,
        })

        return report

    async def get_latest(self) -> SystemSafetyAuditReport | None:
        return self._latest


autonomous_safety_audit_pipeline = AutonomousSafetyAuditPipeline()
