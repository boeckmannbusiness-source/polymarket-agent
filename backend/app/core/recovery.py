import asyncio
from datetime import datetime, timezone

from app.config import settings
from app.redis import get_redis
from app.core.logging import logger


_pending_recovery_tasks: dict[str, asyncio.Task] = {}
_dlq_retry_counts: dict[str, int] = {}


async def recover_pending_messages(
    stream: str,
    group: str,
    consumer: str,
    idle_timeout: int | None = None,
    max_retries: int | None = None,
    dlq_stream: str | None = None,
) -> dict:
    if idle_timeout is None:
        idle_timeout = settings.PENDING_IDLE_TIMEOUT
    if max_retries is None:
        max_retries = settings.PENDING_MAX_RETRIES
    if dlq_stream is None:
        dlq_stream = settings.PENDING_DLQ_STREAM

    r = await get_redis()
    result = {"claimed": 0, "dead_lettered": 0, "pending_total": 0, "errors": 0}

    try:
        pending_summary = await r.xpending(stream, group)
        if not pending_summary:
            return result

        total_pending = pending_summary[0] if isinstance(pending_summary, (list, tuple)) else 0
        result["pending_total"] = total_pending

        if total_pending == 0:
            return result

        idle_ms = idle_timeout * 1000
        claimed = await r.xautoclaim(
            stream, group, consumer,
            min_idle_time=idle_ms,
            count=settings.PENDING_CLAIM_COUNT,
        )
        if claimed and len(claimed) >= 2:
            claimed_ids = claimed[1] if isinstance(claimed[1], list) else []
            for msg_id, msg_data in claimed_ids:
                if isinstance(msg_data, list):
                    msg_data = dict(msg_data)
                msg_str = str(msg_data)
                retry_key = f"retry:{stream}:{group}:{msg_id}"
                retry_count = _dlq_retry_counts.get(retry_key, 0) + 1
                _dlq_retry_counts[retry_key] = retry_count

                if retry_count > max_retries:
                    try:
                        dlq_entry = {
                            "original_stream": stream,
                            "group": group,
                            "msg_id": msg_id,
                            "retry_count": retry_count,
                            "error": "max_retries_exceeded",
                            "data": msg_str[:2000],
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                        await r.xadd(dlq_stream, dlq_entry, maxlen=5000)
                        await r.xack(stream, group, msg_id)
                        result["dead_lettered"] += 1
                        logger.warning(
                            "pel_dlq_transfer",
                            stream=stream, group=group, msg_id=msg_id,
                            retry_count=retry_count,
                        )
                    except Exception as e:
                        logger.error("pel_dlq_failed", error=str(e))
                        result["errors"] += 1
                else:
                    result["claimed"] += 1
                    logger.info(
                        "pel_claimed",
                        stream=stream, group=group, msg_id=msg_id,
                        retry_count=retry_count, idle_ms=idle_ms,
                    )

        return result
    except Exception as e:
        logger.error("pel_recovery_failed", stream=stream, group=group, error=str(e))
        result["errors"] += 1
        return result


async def start_pending_recovery_loop(
    name: str,
    stream: str,
    group: str,
    consumer: str,
    idle_timeout: int = 120,
    max_retries: int = 3,
    interval: int = 60,
):
    if not settings.PENDING_RECOVERY_ENABLED:
        return

    async def _loop():
        await asyncio.sleep(interval)
        while True:
            try:
                result = await recover_pending_messages(
                    stream, group, consumer,
                    idle_timeout=idle_timeout,
                    max_retries=max_retries,
                )
                if result["claimed"] > 0 or result["dead_lettered"] > 0 or result["pending_total"] > 0:
                    logger.info(
                        "pel_recovery_cycle",
                        name=name, stream=stream, group=group,
                        **result,
                    )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("pel_recovery_loop_error", name=name, error=str(e))
            await asyncio.sleep(interval)

    task = asyncio.create_task(_loop(), name=f"pel_recovery_{name}")
    _pending_recovery_tasks[name] = task
    logger.info("pel_recovery_started", name=name, stream=stream, group=group, interval=interval)


async def stop_pending_recovery(name: str):
    task = _pending_recovery_tasks.pop(name, None)
    if task:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


async def stop_all_pending_recovery():
    for name in list(_pending_recovery_tasks.keys()):
        await stop_pending_recovery(name)
