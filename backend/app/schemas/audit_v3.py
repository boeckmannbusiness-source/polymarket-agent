from pydantic import BaseModel
from typing import Any


class ExecutionPathCheck(BaseModel):
    path_name: str
    gated: bool
    details: str = ""


class ExecutionSafetyReport(BaseModel):
    execution_paths: list[ExecutionPathCheck] = []
    all_paths_gated: bool = False
    score: float = 0.0
    risk_flags: list[str] = []
    generated_at: str = ""


class LimitCheck(BaseModel):
    limit_name: str
    limit_value: float
    can_exceed: bool
    details: str = ""


class CapitalProtectionReport(BaseModel):
    limit_checks: list[LimitCheck] = []
    kill_switch_triggers: bool = False
    score: float = 0.0
    risk_flags: list[str] = []
    generated_at: str = ""


class FailClosedScenario(BaseModel):
    scenario: str
    blocks_execution: bool
    details: str = ""


class FailClosedReport(BaseModel):
    scenarios: list[FailClosedScenario] = []
    all_blocked: bool = False
    score: float = 0.0
    risk_flags: list[str] = []
    generated_at: str = ""


class RuntimeEnforcementCheck(BaseModel):
    check_name: str
    blocked: bool
    details: str = ""


class RuntimeEnforcementReport(BaseModel):
    checks: list[RuntimeEnforcementCheck] = []
    all_blocked: bool = False
    score: float = 0.0
    risk_flags: list[str] = []
    generated_at: str = ""


class OperationalReadinessReport(BaseModel):
    logging_score: float = 0.0
    monitoring_score: float = 0.0
    kill_switch_visibility_score: float = 0.0
    overall_score: float = 0.0
    details: dict[str, Any] = {}
    risk_flags: list[str] = []
    generated_at: str = ""


class MicroCapitalReadinessReport(BaseModel):
    execution_safety_score: float = 0.0
    capital_protection_score: float = 0.0
    fail_closed_score: float = 0.0
    runtime_enforcement_score: float = 0.0
    operational_readiness_score: float = 0.0
    overall_score: float = 0.0
    classification: str = "NOT_READY"
    recommendation: str = ""
    risk_summary: str = ""
    generated_at: str = ""


class MicroCapitalAuditReport(BaseModel):
    audit_id: str
    executed_at: str = ""
    execution_safety: ExecutionSafetyReport | None = None
    capital_protection: CapitalProtectionReport | None = None
    fail_closed: FailClosedReport | None = None
    runtime_enforcement: RuntimeEnforcementReport | None = None
    operational_readiness: OperationalReadinessReport | None = None
    micro_capital_readiness: MicroCapitalReadinessReport | None = None
    pipeline_status: str = "completed"
