from fastapi import APIRouter, Query

from app.services.stream.event_store import event_store
from app.services.monitoring.latency_service import latency_tracker
from app.services.stream.deduplication import event_dedup
from app.ws.manager import manager

router = APIRouter()


@router.get("/replay")
async def replay_events(
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    limit: int = Query(default=500, le=5000),
):
    import time
    start = time.time()
    results = await event_store.replay(
        from_ts=from_,
        to_ts=to,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit,
    )
    elapsed = (time.time() - start) * 1000
    latency_tracker.record_replay_latency(elapsed)
    return {"events": results, "count": len(results), "latency_ms": round(elapsed, 2)}


@router.get("/monitoring/latency")
async def latency_metrics():
    return latency_tracker.summary()


@router.get("/monitoring/ws-stats")
async def ws_stats():
    return {
        "connection_count": manager.connection_count,
        "dedup_hit_rate": round(event_dedup.hit_rate, 4),
        "dedup_cache_size": event_dedup.size,
    }
