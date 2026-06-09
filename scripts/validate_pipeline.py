import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from sqlalchemy import select, func
from app.config import settings
from app.redis import get_redis
from app.database import async_session_factory
from app.models.shadow_decision_log import ShadowDecisionLog

async def get_stream_metrics(r):
    streams = [
        "market:data", "wallet:trade", "signal:generated", "trade:request", "trade:execution"
    ]
    metrics = {}
    for stream in streams:
        try:
            info = await r.xinfo_stream(stream)
            metrics[stream] = {
                "length": info["length"],
                "groups": info["groups"]
            }
        except Exception:
            metrics[stream] = {"length": 0, "groups": 0}
    return metrics

async def get_db_metrics():
    async with async_session_factory() as db:
        shadow_count = await db.scalar(select(func.count()).select_from(ShadowDecisionLog))
        last_decisions = await db.execute(select(ShadowDecisionLog).order_by(ShadowDecisionLog.timestamp.desc()).limit(5))
        return {
            "shadow_decision_count": shadow_count,
            "last_decisions": [
                {
                    "strategy": d.strategy_id,
                    "decision": d.safety_gate_decision,
                    "reason": d.rejection_reason or d.approval_reason
                } for d in last_decisions.scalars().all()
            ]
        }

async def run_validation(duration_minutes=15):
    print(f"Starting E2E Validation for {duration_minutes} minutes...")
    r = await get_redis()
    start_time = time.time()

    while (time.time() - start_time) < duration_minutes * 60:
        elapsed = (time.time() - start_time) / 60
        stream_metrics = await get_stream_metrics(r)
        db_metrics = await get_db_metrics()

        print(f"\n--- T+{elapsed:.1f} min ---")
        print("Redis Streams:")
        for s, m in stream_metrics.items():
            print(f"  {s:<20}: {m['length']} entries")

        print(f"Shadow Decisions: {db_metrics['shadow_decision_count']}")
        if db_metrics['last_decisions']:
            print("Last 5 decisions:")
            for d in db_metrics['last_decisions']:
                print(f"  [{d['strategy']}] {d['decision']}: {d['reason']}")

        if db_metrics['shadow_decision_count'] > 0:
             print("\nSUCCESS: At least one shadow decision logged!")

        await asyncio.sleep(30)

if __name__ == "__main__":
    duration = 15
    if len(sys.argv) > 1:
        duration = int(sys.argv[1])
    asyncio.run(run_validation(duration))
