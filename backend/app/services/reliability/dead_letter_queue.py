import json
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Callable

from app.core.logging import logger

DLQ_KEY = "dlq:events"
DLQ_MAXLEN = 50000
DLQ_THRESHOLD_RETRIES = 3
DLQ_THRESHOLD_WINDOW = 300


class DeadLetterQueue:
    def __init__(self):
        self._callbacks: dict[str, Callable] = {}
        self._domain_retry_counts: dict[str, list[float]] = {}
        self._local_backlog: list[dict] = []

    def register_callback(self, domain: str, callback: Callable):
        self._callbacks[domain] = callback

    async def push(self, domain: str, event_type: str, payload: dict, error: str):
        entry = {
            "domain": domain,
            "event_type": event_type,
            "payload": json.dumps(payload, default=str),
            "error": error,
            "retry_count": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._local_backlog.append(entry)
        r = await self._safe_redis()
        if r is not None:
            try:
                await r.xadd(DLQ_KEY, entry, maxlen=DLQ_MAXLEN)
            except Exception:
                pass
        await self._check_threshold(domain)
        logger.warning("dlq_event_stored", domain=domain, event_type=event_type, error=error)

    async def replay(self, domain: str | None = None, limit: int = 100) -> dict:
        replayed = 0
        failed = 0
        skipped = 0

        backlog = list(self._local_backlog)
        for entry in backlog:
            entry_domain = entry.get("domain", "")
            if domain and entry_domain != domain:
                skipped += 1
                continue
            callback = self._callbacks.get(entry_domain)
            if not callback:
                skipped += 1
                continue
            try:
                payload_raw = entry.get("payload", "{}")
                if isinstance(payload_raw, str):
                    payload = json.loads(payload_raw)
                else:
                    payload = payload_raw
                await callback(entry.get("event_type", ""), payload)
                self._local_backlog.remove(entry)
                replayed += 1
            except Exception as e:
                failed += 1
                entry["retry_count"] = int(entry.get("retry_count", 0)) + 1
                entry["error"] = str(e)

        r = await self._safe_redis()
        if r is not None:
            raw = await r.xrevrange(DLQ_KEY, count=limit)
            for msg_id, fields in raw:
                entry = dict(fields)
                entry_domain = entry.get("domain", "")
                if domain and entry_domain != domain:
                    skipped += 1
                    continue
                callback = self._callbacks.get(entry_domain)
                if not callback:
                    skipped += 1
                    continue
                try:
                    payload_raw = entry.get("payload", "{}")
                    if isinstance(payload_raw, str):
                        payload = json.loads(payload_raw)
                    else:
                        payload = payload_raw
                    await callback(entry.get("event_type", ""), payload)
                    await r.xdel(DLQ_KEY, msg_id)
                    replayed += 1
                except Exception as e:
                    failed += 1
                    await self._increment_retry_in_place(r, msg_id, entry, str(e))

        return {"replayed": replayed, "failed": failed, "skipped": skipped}

    async def retry_one(self, msg_id: str) -> bool:
        r = await self._safe_redis()
        if r is None:
            return False
        raw = await r.xrange(DLQ_KEY, min=msg_id, max=msg_id, count=1)
        if not raw:
            return False
        _, fields = raw[0]
        entry = dict(fields)
        callback = self._callbacks.get(entry.get("domain", ""))
        if not callback:
            return False
        try:
            payload_raw = entry.get("payload", "{}")
            if isinstance(payload_raw, str):
                payload = json.loads(payload_raw)
            else:
                payload = payload_raw
            await callback(entry.get("event_type", ""), payload)
            await r.xdel(DLQ_KEY, msg_id)
            return True
        except Exception:
            return False

    async def purge_expired(self, max_age_hours: int = 72):
        r = await self._safe_redis()
        if r is None:
            self._local_backlog.clear()
            return
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_age_hours)).isoformat()
        raw = await r.xrevrange(DLQ_KEY, count=5000)
        deleted = 0
        for msg_id, fields in raw:
            ts = dict(fields).get("timestamp", "")
            if ts < cutoff:
                await r.xdel(DLQ_KEY, msg_id)
                deleted += 1
        if deleted:
            logger.info("dlq_purged_expired", count=deleted)

    async def get_events(self, domain: str | None = None, limit: int = 50) -> list[dict]:
        results = []
        r = await self._safe_redis()
        if r is not None:
            try:
                raw = await r.xrevrange(DLQ_KEY, count=limit)
                for msg_id, fields in raw:
                    entry = dict(fields)
                    entry["msg_id"] = msg_id
                    entry_domain = entry.get("domain", "")
                    if domain and entry_domain != domain:
                        continue
                    try:
                        entry["payload"] = json.loads(entry.get("payload", "{}"))
                    except (json.JSONDecodeError, TypeError):
                        pass
                    results.append(entry)
            except Exception:
                pass
        for local in self._local_backlog:
            if domain and local.get("domain") != domain:
                continue
            results.append(dict(local))
        return results[:limit]

    async def get_stats(self) -> dict:
        total = len(self._local_backlog)
        by_domain: dict[str, int] = {}
        retry_counts: list[int] = []
        oldest = datetime.now(timezone.utc).isoformat()
        r = await self._safe_redis()
        if r is not None:
            try:
                raw = await r.xrevrange(DLQ_KEY, count=5000)
                for _, fields in raw:
                    entry = dict(fields)
                    d = entry.get("domain", "unknown")
                    by_domain[d] = by_domain.get(d, 0) + 1
                    rc = int(entry.get("retry_count", 0))
                    retry_counts.append(rc)
                    ts = entry.get("timestamp", "")
                    if ts and ts < oldest:
                        oldest = ts
                total = sum(by_domain.values())
            except Exception:
                pass
        for local in self._local_backlog:
            d = local.get("domain", "unknown")
            by_domain[d] = by_domain.get(d, 0) + 1
            ts = local.get("timestamp", "")
            if ts and ts < oldest:
                oldest = ts
        return {
            "total_events": total,
            "by_domain": by_domain,
            "retry_counts": retry_counts[:10],
            "oldest_event_age_hours": round((datetime.now(timezone.utc) - datetime.fromisoformat(oldest)).total_seconds() / 3600, 2) if oldest else 0,
        }

    async def _check_threshold(self, domain: str):
        now = time.time()
        self._domain_retry_counts.setdefault(domain, []).append(now)
        self._domain_retry_counts[domain] = [t for t in self._domain_retry_counts[domain] if now - t < DLQ_THRESHOLD_WINDOW]
        if len(self._domain_retry_counts[domain]) >= DLQ_THRESHOLD_RETRIES:
            try:
                from app.services.incidents.incident_service import incident_service as _is
                await _is.create_from_alert(
                    alert_data={
                        "title": f"DLQ threshold breached: {domain}",
                        "severity": "warning",
                        "message": f"{DLQ_THRESHOLD_RETRIES}+ failed events in {DLQ_THRESHOLD_WINDOW}s on domain '{domain}'",
                    }
                )
            except Exception:
                pass
            self._domain_retry_counts[domain] = []

    async def _increment_retry_in_place(self, r, msg_id: str, entry: dict, error: str):
        try:
            entry["retry_count"] = int(entry.get("retry_count", 0)) + 1
            entry["error"] = error
            entry["last_retry"] = datetime.now(timezone.utc).isoformat()
            await r.xadd(DLQ_KEY, entry, maxlen=DLQ_MAXLEN)
            await r.xdel(DLQ_KEY, msg_id)
        except Exception:
            pass

    async def _safe_redis(self):
        try:
            from app.redis import get_redis
            return await get_redis()
        except Exception:
            return None


dlq = DeadLetterQueue()
