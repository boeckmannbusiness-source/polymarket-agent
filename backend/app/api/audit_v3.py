from fastapi import APIRouter

from app.services.audit_v3.execution_safety_audit import execution_safety_audit
from app.services.audit_v3.capital_protection_audit import capital_protection_audit
from app.services.audit_v3.fail_closed_audit import fail_closed_audit
from app.services.audit_v3.runtime_enforcement_audit import runtime_enforcement_audit
from app.services.audit_v3.operational_readiness_audit import operational_readiness_audit
from app.services.audit_v3.micro_capital_readiness_pipeline import micro_capital_readiness_pipeline

router = APIRouter()


@router.get("/micro-capital/execution")
async def get_execution_safety():
    report = await execution_safety_audit.get_latest()
    if report is None:
        report = await execution_safety_audit.audit()
    return report.model_dump()


@router.get("/micro-capital/capital")
async def get_capital_protection():
    report = await capital_protection_audit.get_latest()
    if report is None:
        report = await capital_protection_audit.audit()
    return report.model_dump()


@router.get("/micro-capital/fail-closed")
async def get_fail_closed():
    report = await fail_closed_audit.get_latest()
    if report is None:
        report = await fail_closed_audit.audit()
    return report.model_dump()


@router.get("/micro-capital/runtime")
async def get_runtime_enforcement():
    report = await runtime_enforcement_audit.get_latest()
    if report is None:
        report = await runtime_enforcement_audit.audit()
    return report.model_dump()


@router.get("/micro-capital/operational")
async def get_operational_readiness():
    report = await operational_readiness_audit.get_latest()
    if report is None:
        report = await operational_readiness_audit.audit()
    return report.model_dump()


@router.get("/micro-capital/readiness")
async def get_readiness():
    report = await micro_capital_readiness_pipeline.get_latest()
    if report is None:
        full = await micro_capital_readiness_pipeline.run()
        return full.micro_capital_readiness.model_dump() if full.micro_capital_readiness else {}
    return report.micro_capital_readiness.model_dump() if report.micro_capital_readiness else {}


@router.post("/micro-capital/run")
async def run_micro_capital_audit():
    report = await micro_capital_readiness_pipeline.run()
    return report.model_dump()
