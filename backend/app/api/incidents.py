from fastapi import APIRouter, Query

from app.services.incidents.incident_service import incident_service
from app.services.risk.circuit_breakers import cb_system

router = APIRouter()


@router.get("")
async def list_incidents(limit: int = Query(default=50, le=200)):
    incidents = await incident_service.get_all(limit=limit)
    stats = await incident_service.get_stats()
    return {"incidents": incidents, "stats": stats, "count": len(incidents)}


@router.get("/{incident_id}")
async def get_incident(incident_id: str):
    incident = await incident_service.get(incident_id)
    if not incident:
        return {"error": "Not found"}
    return incident


@router.post("/{incident_id}/investigate")
async def investigate_incident(incident_id: str):
    ok = await incident_service.update_status(incident_id, "investigating")
    return {"ok": ok}


@router.post("/{incident_id}/mitigate")
async def mitigate_incident(incident_id: str):
    ok = await incident_service.update_status(incident_id, "mitigated")
    return {"ok": ok}


@router.post("/{incident_id}/resolve")
async def resolve_incident(incident_id: str):
    ok = await incident_service.update_status(incident_id, "resolved")
    return {"ok": ok}


@router.get("/breakers/active")
async def active_breakers():
    return {"breakers": await cb_system.get_active()}


@router.post("/breakers/reset/{name}")
async def reset_breaker(name: str):
    await cb_system.reset_one(name)
    return {"ok": True}


@router.post("/breakers/reset")
async def reset_all_breakers():
    await cb_system.reset_all()
    return {"ok": True}
