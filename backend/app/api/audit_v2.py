from fastapi import APIRouter

from app.services.audit_v2.system_safety_audit_service import system_safety_audit_service
from app.services.audit_v2.data_integrity_audit_service import data_integrity_audit_service
from app.services.audit_v2.feedback_cycle_check_service import feedback_cycle_check_service
from app.services.audit_v2.stress_safety_simulator import stress_safety_simulator
from app.services.audit_v2.production_gate_service import production_gate_service
from app.services.audit_v2.autonomous_safety_audit_pipeline import autonomous_safety_audit_pipeline

router = APIRouter()


@router.get("/safety/system")
async def get_system_safety():
    report = await system_safety_audit_service.get_latest()
    if report is None:
        report = await system_safety_audit_service.audit()
    return report.model_dump()


@router.get("/safety/data")
async def get_data_integrity():
    report = await data_integrity_audit_service.get_latest()
    if report is None:
        report = await data_integrity_audit_service.audit()
    return report.model_dump()


@router.get("/safety/cycles")
async def get_feedback_cycles():
    report = await feedback_cycle_check_service.get_latest()
    if report is None:
        report = await feedback_cycle_check_service.check()
    return report.model_dump()


@router.get("/safety/stress")
async def get_stress_safety():
    report = await stress_safety_simulator.get_latest()
    if report is None:
        report = await stress_safety_simulator.simulate()
    return report.model_dump()


@router.get("/safety/readiness")
async def get_readiness():
    report = await production_gate_service.get_latest()
    if report is None:
        # Need to run full pipeline first
        full = await autonomous_safety_audit_pipeline.run()
        return full.production_gate.model_dump() if full.production_gate else {}
    return report.model_dump()


@router.post("/safety/run")
async def run_safety_audit():
    report = await autonomous_safety_audit_pipeline.run()
    return report.model_dump()
