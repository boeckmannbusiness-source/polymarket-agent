from pydantic import BaseModel
from typing import Any


class ComponentEntry(BaseModel):
    name: str
    classification: str  # deterministic | stochastic | adaptive
    depends_on: list[str] = []


class DependencyGraph(BaseModel):
    nodes: list[ComponentEntry] = []
    adjacency: dict[str, list[str]] = {}


class CriticalPath(BaseModel):
    path: list[str]
    length: int


class SinglePointOfFailure(BaseModel):
    component: str
    reason: str
    downstream_count: int


class CouplingRisk(BaseModel):
    components: list[str]
    risk_type: str
    description: str = ""


class SystemSafetyReport(BaseModel):
    components: list[ComponentEntry] = []
    adjacency: dict[str, list[str]] = {}
    critical_paths: list[CriticalPath] = []
    single_points_of_failure: list[SinglePointOfFailure] = []
    coupling_risks: list[CouplingRisk] = []
    risk_flags: list[str] = []
    generated_at: str = ""


class SignalHealthEntry(BaseModel):
    source: str
    freshness_hours: float = 0.0
    stability_score: float = 0.0
    missingness_pct: float = 0.0
    source_type: str = ""  # internal_computed | external_derived | synthetic
    health_score: float = 0.0


class DataIntegrityReport(BaseModel):
    signals: list[SignalHealthEntry] = []
    overall_data_quality_score: float = 0.0
    risk_flags: list[str] = []
    generated_at: str = ""


class FeedbackCycle(BaseModel):
    cycle: list[str]
    cycle_length: int
    risk_level: str  # LOW | MEDIUM | HIGH


class FeedbackCycleReport(BaseModel):
    cycles: list[FeedbackCycle] = []
    overall_risk_level: str = "LOW"
    risk_flags: list[str] = []
    generated_at: str = ""


class StressScenarioResult(BaseModel):
    scenario_id: str
    scenario_type: str
    allocation_deviation: float = 0.0
    max_drawdown_estimate: float = 0.0
    recovery_sensitivity: str = ""  # low | medium | high
    details: dict[str, Any] = {}


class StressSafetyReport(BaseModel):
    scenario_results: list[StressScenarioResult] = []
    worst_case_scenario: str = ""
    overall_stress_score: float = 100.0
    risk_flags: list[str] = []
    generated_at: str = ""


class ProductionGateReport(BaseModel):
    overall_score: float = 0.0
    stability_score: float = 0.0
    data_score: float = 0.0
    stress_score: float = 0.0
    classification: str = "NOT_READY"
    risk_summary: str = ""
    recommendation: str = ""
    generated_at: str = ""


class SystemSafetyAuditReport(BaseModel):
    audit_id: str
    executed_at: str = ""
    system_safety: SystemSafetyReport | None = None
    data_integrity: DataIntegrityReport | None = None
    feedback_cycles: FeedbackCycleReport | None = None
    stress_safety: StressSafetyReport | None = None
    production_gate: ProductionGateReport | None = None
    pipeline_status: str = "completed"
