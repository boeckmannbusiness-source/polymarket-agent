import time
from datetime import datetime, timezone
from typing import Any, Callable

from app.core.logging import logger
from app.redis import get_redis
from app.ws.manager import manager
from app.services.control.control_plane import control_plane
from app.services.audit.audit_logger import emit

CB_PREFIX = "circuit_breaker:"
CB_REGISTRY_KEY = f"{CB_PREFIX}registry"
CB_ACTIVE_KEY = f"{CB_PREFIX}active"


async def _safe_redis():
    try:
        return await get_redis()
    except Exception:
        return None


class CircuitBreaker:
    def __init__(self, name: str, check_fn: Callable[[], tuple[bool, str]], cooldown: int = 300):
        self.name = name
        self.check_fn = check_fn
        self.cooldown = cooldown
        self._local_trigger: dict | None = None

    async def is_triggered(self) -> bool:
        if self._local_trigger is not None:
            if time.time() - self._local_trigger.get("triggered_at", 0) < self.cooldown:
                return True
            self._local_trigger = None
        r = await _safe_redis()
        if r is None:
            return False
        try:
            val = await r.hget(CB_ACTIVE_KEY, self.name)
            if not val:
                return False
            data = eval(val.decode())
            return time.time() - data.get("triggered_at", 0) < self.cooldown
        except Exception:
            return False

    async def evaluate(self, context: dict[str, Any]) -> dict | None:
        if await self.is_triggered():
            return None
        triggered, reason = self.check_fn()
        if not triggered:
            return None
        return await self._trigger(reason)

    async def _trigger(self, reason: str) -> dict:
        now = datetime.now(timezone.utc)
        entry = {
            "name": self.name,
            "reason": reason,
            "triggered_at": time.time(),
            "timestamp": now.isoformat(),
            "cooldown": self.cooldown,
        }
        self._local_trigger = entry
        r = await _safe_redis()
        if r is not None:
            try:
                await r.hset(CB_ACTIVE_KEY, self.name, str(entry))
            except Exception:
                pass
        await self._broadcast(entry)
        await emit("breaker.triggered", "circuit_breaker", self.name, {"reason": reason, "cooldown": self.cooldown})
        logger.critical("circuit_breaker_triggered", name=self.name, reason=reason)
        return entry

    async def reset(self):
        self._local_trigger = None
        r = await _safe_redis()
        if r is not None:
            try:
                await r.hdel(CB_ACTIVE_KEY, self.name)
            except Exception:
                pass
        await self._broadcast({"name": self.name, "status": "reset"})
        await emit("breaker.reset", "circuit_breaker", self.name, {})
        logger.info("circuit_breaker_reset", name=self.name)

    async def _broadcast(self, data: dict):
        event = {
            "event_id": f"cb:{self.name}:{datetime.now(timezone.utc).isoformat()}",
            "event_type": "circuit_breaker_triggered" if "reason" in data else "circuit_breaker_reset",
            "entity_type": "circuit_breaker",
            "entity_id": self.name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": data,
        }
        await manager.broadcast_event(event, channels=["control", "monitoring", "alerts"])


class CircuitBreakerSystem:
    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}

    def register(self, breaker: CircuitBreaker):
        self._breakers[breaker.name] = breaker

    async def evaluate_all(self, context: dict[str, Any]) -> list[dict]:
        triggered = []
        for name, breaker in self._breakers.items():
            result = await breaker.evaluate(context)
            if result:
                triggered.append(result)
                action = self._get_action(name)
                if action:
                    await action(context)
        return triggered

    async def get_active(self) -> list[dict]:
        results = []
        for breaker in self._breakers.values():
            if await breaker.is_triggered():
                r = await _safe_redis()
                if r is not None:
                    try:
                        val = await r.hget(CB_ACTIVE_KEY, breaker.name)
                        if val:
                            data = eval(val.decode())
                            results.append(data)
                            continue
                    except Exception:
                        pass
                results.append({"name": breaker.name, "reason": "local_trigger", "triggered_at": time.time(), "cooldown": breaker.cooldown})
        return results

    async def reset_all(self):
        for breaker in self._breakers.values():
            await breaker.reset()

    async def reset_one(self, name: str):
        if name in self._breakers:
            await self._breakers[name].reset()

    def _get_action(self, name: str) -> Callable | None:
        actions = {
            "loss_circuit": lambda ctx: control_plane.set_trading_enabled(False),
            "execution_failure": lambda ctx: control_plane.set_execution_mode("paper"),
            "latency_spike": lambda ctx: control_plane.set_execution_mode("shadow"),
            "drift_breaker": lambda ctx: control_plane.set_trading_enabled(False),
        }
        return actions.get(name)


cb_system = CircuitBreakerSystem()


def register_default_breakers():
    def loss_check():
        return False, ""

    def exec_fail_check():
        return False, ""

    def latency_check():
        return False, ""

    def drift_check():
        return False, ""

    cb_system.register(CircuitBreaker("loss_circuit", loss_check, cooldown=600))
    cb_system.register(CircuitBreaker("execution_failure", exec_fail_check, cooldown=300))
    cb_system.register(CircuitBreaker("latency_spike", latency_check, cooldown=300))
    cb_system.register(CircuitBreaker("drift_breaker", drift_check, cooldown=600))
