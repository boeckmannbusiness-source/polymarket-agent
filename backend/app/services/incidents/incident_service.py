import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.logging import logger
from app.redis import get_redis
from app.ws.manager import manager

INCIDENTS_KEY = "incidents"


async def _safe_redis():
    try:
        return await get_redis()
    except Exception:
        return None


class IncidentService:
    def __init__(self):
        self._local_incidents: dict[str, dict] = {}
        self._max_incidents = 500

    async def create_from_alert(self, alert: dict[str, Any]) -> dict[str, Any]:
        incident = {
            "id": str(uuid.uuid4()),
            "title": alert.get("title", "Alert triggered"),
            "description": alert.get("message", ""),
            "severity": alert.get("severity", "info"),
            "source": "alert",
            "source_id": alert.get("id", ""),
            "entity_id": alert.get("entity_id", ""),
            "entity_type": alert.get("rule", "unknown"),
            "linked_alerts": [alert.get("id", "")],
            "linked_trades": [],
            "linked_fills": [],
            "linked_strategies": [],
            "status": "open",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "resolved_at": None,
        }
        await self._store(incident)
        await self._broadcast(incident)
        logger.info("incident_created", id=incident["id"], severity=incident["severity"])
        return incident

    async def create_from_breaker(self, breaker_data: dict[str, Any]) -> dict[str, Any]:
        incident = {
            "id": str(uuid.uuid4()),
            "title": f"Circuit breaker: {breaker_data.get('name', 'unknown')}",
            "description": breaker_data.get("reason", "Circuit breaker triggered"),
            "severity": "critical",
            "source": "circuit_breaker",
            "source_id": breaker_data.get("name", ""),
            "entity_id": "system",
            "entity_type": "circuit_breaker",
            "linked_alerts": [],
            "linked_trades": [],
            "linked_fills": [],
            "linked_strategies": [],
            "status": "open",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "resolved_at": None,
        }
        await self._store(incident)
        await self._broadcast(incident)
        logger.critical("incident_created_from_breaker", id=incident["id"], name=breaker_data.get("name"))
        return incident

    async def get(self, incident_id: str) -> dict | None:
        if incident_id in self._local_incidents:
            return self._local_incidents[incident_id]
        r = await _safe_redis()
        if r is None:
            return None
        raw = await r.hget(INCIDENTS_KEY, incident_id)
        if raw:
            return eval(raw.decode())
        return None

    async def get_all(self, limit: int = 50) -> list[dict]:
        incidents = list(self._local_incidents.values())
        r = await _safe_redis()
        if r is not None:
            try:
                raw = await r.hgetall(INCIDENTS_KEY)
                seen_ids = {i["id"] for i in incidents}
                for val in raw.values():
                    try:
                        data = eval(val.decode()) if isinstance(val, bytes) else eval(val)
                        if data["id"] not in seen_ids:
                            incidents.append(data)
                            seen_ids.add(data["id"])
                    except Exception:
                        pass
            except Exception:
                pass
        incidents.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return incidents[:limit]

    async def update_status(self, incident_id: str, new_status: str) -> bool:
        incident = await self.get(incident_id)
        if not incident:
            return False
        valid = ("open", "investigating", "mitigated", "resolved")
        if new_status not in valid:
            return False
        incident["status"] = new_status
        incident["updated_at"] = datetime.now(timezone.utc).isoformat()
        if new_status == "resolved":
            incident["resolved_at"] = datetime.now(timezone.utc).isoformat()
        await self._store(incident)
        await self._broadcast(incident)
        logger.info("incident_status_updated", id=incident_id, status=new_status)
        return True

    async def link_trade(self, incident_id: str, trade_id: str) -> bool:
        incident = await self.get(incident_id)
        if not incident:
            return False
        if trade_id not in incident["linked_trades"]:
            incident["linked_trades"].append(trade_id)
            incident["updated_at"] = datetime.now(timezone.utc).isoformat()
            await self._store(incident)
        return True

    async def link_alert(self, incident_id: str, alert_id: str) -> bool:
        incident = await self.get(incident_id)
        if not incident:
            return False
        if alert_id not in incident["linked_alerts"]:
            incident["linked_alerts"].append(alert_id)
            incident["updated_at"] = datetime.now(timezone.utc).isoformat()
            await self._store(incident)
        return True

    async def get_stats(self) -> dict[str, int]:
        incidents = await self.get_all(limit=500)
        stats = {"total": len(incidents), "open": 0, "investigating": 0, "mitigated": 0, "resolved": 0}
        for inc in incidents:
            s = inc.get("status", "open")
            if s in stats:
                stats[s] += 1
        return stats

    async def _store(self, incident: dict):
        self._local_incidents[incident["id"]] = incident
        r = await _safe_redis()
        if r is not None:
            try:
                await r.hset(INCIDENTS_KEY, incident["id"], str(incident))
            except Exception:
                pass
        if len(self._local_incidents) > self._max_incidents:
            oldest = min(self._local_incidents.keys(), key=lambda k: self._local_incidents[k].get("created_at", ""))
            self._local_incidents.pop(oldest, None)

    async def _broadcast(self, incident: dict):
        event = {
            "event_id": f"incident:{incident['id']}",
            "event_type": "incident.updated",
            "entity_type": "incident",
            "entity_id": incident["id"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": incident,
        }
        await manager.broadcast_event(event, channels=["control", "alerts"])


incident_service = IncidentService()
