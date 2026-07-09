import enum
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.logging import logger
from app.core.metrics import system_mode_gauge, mode_transitions_total
from app.core.mode_context import MODE_CONTEXTS, get_hold_time
from app.core.state_store import get_state_store


_REDIS_KEY = "system:mode"
_LOCAL_CACHE: dict[str, Any] = {"mode": "normal", "reason": "", "updated_at": 0}

_manager: "ModeManager | None" = None


def set_global_manager(mgr: "ModeManager"):
    global _manager
    _manager = mgr


def get_mode_manager() -> "ModeManager":
    if _manager is None:
        raise RuntimeError("ModeManager not initialized")
    return _manager


class SystemMode(str, enum.Enum):
    NORMAL = "normal"
    SHADOW = "shadow"
    DEGRADED = "degraded"
    PROTECTED = "protected"
    READ_ONLY = "read_only"
    EMERGENCY_STOP = "emergency_stop"

    def __ge__(self, other):
        order = list(SystemMode)
        return order.index(self) >= order.index(other)

    def __gt__(self, other):
        order = list(SystemMode)
        return order.index(self) > order.index(other)

    def __le__(self, other):
        order = list(SystemMode)
        return order.index(self) <= order.index(other)

    def __lt__(self, other):
        order = list(SystemMode)
        return order.index(self) < order.index(other)


_MODE_ORDER = [SystemMode.NORMAL, SystemMode.SHADOW, SystemMode.DEGRADED, SystemMode.PROTECTED, SystemMode.READ_ONLY, SystemMode.EMERGENCY_STOP]


@dataclass
class ModeSnapshot:
    mode: SystemMode
    reason: str
    updated_at: float
    triggered_by: list[str] = field(default_factory=list)
    ttl_seconds: int | None = None
    is_manual_override: bool = False
    operator: str = ""


class ModeManager:
    def __init__(self):
        self._override: ModeSnapshot | None = None
        self._mode = SystemMode.NORMAL
        self._reason = ""
        self._last_transition_time = 0.0
        self._minimum_duration: dict[SystemMode, float] = {
            SystemMode.NORMAL: 120.0,
            SystemMode.DEGRADED: 60.0,
            SystemMode.PROTECTED: 60.0,
            SystemMode.READ_ONLY: 30.0,
            SystemMode.EMERGENCY_STOP: 10.0,
        }

        self._vote_counts: dict[SystemMode, list[dict]] = defaultdict(list)
        self._entry_time: dict[SystemMode, float] = {}

    async def get_mode(self) -> SystemMode:
        if self._override and self._is_override_valid():
            return self._override.mode
        return self._mode

    def get_context(self):
        from app.core.mode_context import MODE_CONTEXTS
        return MODE_CONTEXTS[self._mode.value]

    async def get_snapshot(self) -> ModeSnapshot:
        if self._override and self._is_override_valid():
            return self._override
        return ModeSnapshot(
            mode=self._mode,
            reason=self._reason,
            updated_at=self._last_transition_time or time.monotonic(),
        )

    def _is_override_valid(self) -> bool:
        if not self._override:
            return False
        if self._override.ttl_seconds:
            elapsed = time.monotonic() - self._override.updated_at
            if elapsed >= self._override.ttl_seconds:
                self._override = None
                return False
        return True

    async def request_mode(
        self,
        target: SystemMode,
        reason: str,
        source: str = "",
        severity: float = 50,
    ):
        self._vote_counts[target].append({
            "reason": reason,
            "source": source,
            "severity": severity,
            "timestamp": time.monotonic(),
        })

    async def set_manual_override(
        self,
        mode: SystemMode,
        reason: str,
        operator: str = "",
        ttl_seconds: int = 300,
    ):
        self._override = ModeSnapshot(
            mode=mode,
            reason=reason,
            updated_at=time.monotonic(),
            triggered_by=["manual_override"],
            ttl_seconds=ttl_seconds,
            is_manual_override=True,
            operator=operator,
        )
        await self._persist(mode, f"manual_override:{reason}")
        await self.record_transition_db(
            from_mode=self._mode.value, to_mode=mode.value, reason=reason,
            is_manual=True, operator=operator,
        )
        logger.warning("system_mode_manual_override", mode=mode.value, reason=reason, operator=operator, ttl=ttl_seconds)

    async def clear_manual_override(self):
        if self._override:
            logger.info("system_mode_override_cleared", previous=self._override.mode.value)
            self._override = None

    async def evaluate(self, health_metrics: dict) -> SystemMode:
        if self._override and self._is_override_valid():
            return self._override.mode

        now = time.monotonic()
        self._prune_stale_votes(now)

        proposed = self._compute_mode_from_metrics(health_metrics)
        proposed = await self._apply_hysteresis(proposed, now)

        if proposed != self._mode:
            await self._transition(proposed, self._reason or proposed.value, health_metrics)
        elif not self._reason:
            self._reason = proposed.value

        self._vote_counts.clear()
        return self._mode

    def _prune_stale_votes(self, now: float):
        for mode in list(self._vote_counts.keys()):
            self._vote_counts[mode] = [
                v for v in self._vote_counts[mode]
                if now - v["timestamp"] < 30.0
            ]
            if not self._vote_counts[mode]:
                del self._vote_counts[mode]

    def _compute_mode_from_metrics(self, m: dict) -> SystemMode:
        ctx = MODE_CONTEXTS[self._mode.value]

        if m.get("emergency_stop", False) or m.get("kill_switch", False):
            self._reason = "emergency_stop_activated"
            return SystemMode.EMERGENCY_STOP

        if m.get("circuit_breaker_open", False):
            self._reason = "circuit_breaker_open"
            return SystemMode.PROTECTED

        db_util = m.get("db_pool_utilization_pct", 0)
        if db_util >= ctx.db_pool_critical * 100:
            self._reason = f"db_pool_{db_util}%_critical"
            return SystemMode.PROTECTED

        redis_mem = m.get("redis_memory_pct", 0)
        if redis_mem >= ctx.redis_memory_critical * 100:
            self._reason = f"redis_memory_{redis_mem}%_critical"
            return SystemMode.PROTECTED

        if m.get("drawdown", 0) > 0.15:
            self._reason = f"drawdown_{m['drawdown']:.2%}"
            return SystemMode.PROTECTED

        stream_ratio = m.get("stream_pressure_ratio", 0)
        if stream_ratio >= ctx.stream_critical_ratio:
            self._reason = f"stream_pressure_{stream_ratio:.0%}_critical"
            return SystemMode.PROTECTED

        if db_util >= ctx.db_pool_warning * 100:
            self._reason = f"db_pool_{db_util}%_warning"
            return SystemMode.DEGRADED

        redis_pending = m.get("redis_max_pending", 0)
        if redis_pending > 500:
            self._reason = f"redis_pending_{redis_pending}"
            return SystemMode.DEGRADED

        reconnects = m.get("reconnect_storm", 0)
        if reconnects > 5:
            self._reason = f"reconnect_storm_{reconnects}_per_min"
            return SystemMode.DEGRADED

        if stream_ratio >= ctx.stream_warning_ratio:
            self._reason = f"stream_pressure_{stream_ratio:.0%}_warning"
            return SystemMode.DEGRADED

        self._reason = "all_healthy"
        return SystemMode.NORMAL

    async def _apply_hysteresis(self, target: SystemMode, now: float) -> SystemMode:
        current = self._mode
        if target == current:
            return target

        target_idx = _MODE_ORDER.index(target)
        current_idx = _MODE_ORDER.index(current)

        if target_idx > current_idx:
            if target == SystemMode.EMERGENCY_STOP:
                return target
            if current in self._entry_time:
                elapsed = now - self._entry_time[current]
                hold = get_hold_time(current.value)
                if elapsed < hold:
                    return current
            return target

        if current not in self._entry_time:
            return target

        elapsed = now - self._entry_time[current]
        min_dur = self._minimum_duration.get(current, 60.0)
        if elapsed < min_dur:
            return current

        downgrade_map = {
            SystemMode.PROTECTED: SystemMode.DEGRADED,
            SystemMode.DEGRADED: SystemMode.NORMAL,
        }
        if current in downgrade_map and target != downgrade_map[current]:
            return downgrade_map[current]

        return target

    async def _transition(self, target: SystemMode, reason: str, trigger_metrics: dict | None = None):
        previous = self._mode
        self._mode = target
        self._reason = reason
        self._last_transition_time = time.monotonic()
        self._entry_time[target] = time.monotonic()

        system_mode_gauge.labels(mode=target.value).set(1)
        if previous != target:
            system_mode_gauge.labels(mode=previous.value).set(0)
        mode_transitions_total.labels(from_mode=previous.value, to_mode=target.value).inc()

        await self._persist(target, reason)
        await self.record_transition_db(
            from_mode=previous.value, to_mode=target.value, reason=reason,
            trigger_metrics=trigger_metrics,
        )
        logger.warning("system_mode_transition", from_mode=previous.value, to_mode=target.value, reason=reason)

    async def _persist(self, mode: SystemMode, reason: str):
        try:
            store = await get_state_store()
            payload = json.dumps({"mode": mode.value, "reason": reason, "updated_at": time.monotonic()})
            await store.set(_REDIS_KEY, payload, ex=3600)
            _LOCAL_CACHE["mode"] = mode.value
            _LOCAL_CACHE["reason"] = reason
            _LOCAL_CACHE["updated_at"] = time.monotonic()
        except Exception as e:
            logger.error("mode_persist_failed", error=str(e))

    async def load_from_store(self):
        try:
            store = await get_state_store()
            raw = await store.get(_REDIS_KEY)
            if raw:
                data = json.loads(raw)
                self._mode = SystemMode(data.get("mode", "normal"))
                self._reason = data.get("reason", "")
                self._last_transition_time = data.get("updated_at", 0)
                _LOCAL_CACHE["mode"] = self._mode.value
        except Exception:
            pass

    def can_process(self) -> bool:
        return self._mode not in (SystemMode.EMERGENCY_STOP, SystemMode.READ_ONLY)

    def can_write(self) -> bool:
        return self._mode not in (
            SystemMode.EMERGENCY_STOP, SystemMode.READ_ONLY, SystemMode.PROTECTED
        )

    def can_execute_trades(self) -> bool:
        return self._mode == SystemMode.NORMAL

    def is_shadow(self) -> bool:
        return self._mode == SystemMode.SHADOW

    def can_recover(self) -> bool:
        return self._mode not in (SystemMode.EMERGENCY_STOP, SystemMode.READ_ONLY)

    async def record_transition_db(self, from_mode: str, to_mode: str, reason: str,
                                       trigger_metrics: dict | None = None,
                                       duration_seconds: float | None = None,
                                       is_manual: bool = False,
                                       operator: str = ""):
        try:
            from app.models.system_mode import SystemModeTransition
            from app.database import async_session_factory
            async with async_session_factory() as db:
                record = SystemModeTransition(
                    from_mode=from_mode,
                    to_mode=to_mode,
                    reason=reason,
                    trigger_metrics=trigger_metrics,
                    duration_seconds=duration_seconds,
                    is_manual=is_manual,
                    operator=operator,
                )
                db.add(record)
                await db.commit()
        except Exception as e:
            logger.warning("mode_transition_db_failed", error=str(e))
