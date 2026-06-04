from fastapi import APIRouter

from app.services.research.signal_registry import signal_registry
from app.services.research.research_orchestrator import orchestrator

router = APIRouter()


@router.get("/signals")
async def get_signals(lifecycle: str | None = None):
    signals = await signal_registry.get_all(lifecycle=lifecycle)
    return {"signals": [s.model_dump() for s in signals]}


@router.get("/consensus")
async def get_consensus():
    all_signals = await signal_registry.get_all()
    approved = [s for s in all_signals if s.lifecycle == "consensus_approved"]
    rejected = [s for s in all_signals if s.lifecycle == "consensus_rejected"]
    pending = [s for s in all_signals if s.lifecycle in ("generated", "scored", "meta_reviewed")]
    return {
        "approved_count": len(approved),
        "rejected_count": len(rejected),
        "pending_count": len(pending),
        "approved": [s.model_dump() for s in approved],
        "rejected": [s.model_dump() for s in rejected],
        "pending": [s.model_dump() for s in pending],
    }


@router.get("/health")
async def get_agent_health():
    health = await orchestrator.get_agent_health()
    return {"agents": health}


@router.get("/registry")
async def get_registry():
    stats = await signal_registry.get_stats()
    agent_counts = await signal_registry.get_agent_counts()
    return {"stats": stats, "agent_counts": agent_counts}


@router.post("/run")
async def run_research():
    result = await orchestrator.run_pipeline()
    return result


@router.get("/status")
async def get_status():
    status = await orchestrator.get_status()
    return status