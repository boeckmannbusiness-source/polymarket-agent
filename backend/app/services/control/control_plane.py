from datetime import datetime, timezone
from typing import Any
from collections import defaultdict

from app.redis import get_redis
from app.core.logging import logger
from app.ws.manager import manager
from app.services.audit.audit_logger import emit

CONTROL_PREFIX = "control:"
TRADING_KEY = f"{CONTROL_PREFIX}trading_enabled"
EXECUTION_MODE_KEY = f"{CONTROL_PREFIX}execution_mode"
PAUSED_STRATEGIES_KEY = f"{CONTROL_PREFIX}paused_strategies"
PAUSED_MARKETS_KEY = f"{CONTROL_PREFIX}paused_markets"
CIRCUIT_BREAKERS_KEY = f"{CONTROL_PREFIX}circuit_breakers"


class ControlPlane:
    def __init__(self):
        self._local_paused_strategies: set[str] = set()
        self._local_paused_markets: set[str] = set()
        self._local_trading_enabled = True
        self._local_execution_mode = "paper"

    async def _redis_or(self, default):
        try:
            r = await get_redis()
            return r
        except Exception:
            return None

    async def is_trading_enabled(self) -> bool:
        r = await self._redis_or(None)
        if r is None:
            return self._local_trading_enabled
        try:
            val = await r.get(TRADING_KEY)
            return val != b"false"
        except Exception:
            return self._local_trading_enabled

    async def set_trading_enabled(self, enabled: bool):
        self._local_trading_enabled = enabled
        r = await self._redis_or(None)
        if r is not None:
            try:
                val = "true" if enabled else "false"
                await r.set(TRADING_KEY, val)
            except Exception:
                pass
        await self._broadcast_state_change("trading_enabled", {"enabled": enabled})
        await emit("control.trading_changed", "control", "system", {"enabled": enabled})
        logger.info("control_trading_enabled", enabled=enabled)

    async def get_execution_mode(self) -> str:
        r = await self._redis_or(None)
        if r is None:
            return self._local_execution_mode
        try:
            val = await r.get(EXECUTION_MODE_KEY)
            return (val or b"paper").decode()
        except Exception:
            return self._local_execution_mode

    async def set_execution_mode(self, mode: str):
        if mode not in ("paper", "live", "shadow"):
            raise ValueError(f"Invalid mode: {mode}")
        self._local_execution_mode = mode
        r = await self._redis_or(None)
        if r is not None:
            try:
                await r.set(EXECUTION_MODE_KEY, mode)
            except Exception:
                pass
        await self._broadcast_state_change("execution_mode", {"mode": mode})
        await emit("control.mode_changed", "control", "system", {"mode": mode})
        logger.info("control_execution_mode", mode=mode)

    async def is_strategy_paused(self, strategy_id: str) -> bool:
        if strategy_id in self._local_paused_strategies:
            return True
        r = await self._redis_or(None)
        if r is None:
            return False
        try:
            member = await r.sismember(PAUSED_STRATEGIES_KEY, strategy_id)
            return bool(member)
        except Exception:
            return False

    async def pause_strategy(self, strategy_id: str):
        self._local_paused_strategies.add(strategy_id)
        r = await self._redis_or(None)
        if r is not None:
            try:
                await r.sadd(PAUSED_STRATEGIES_KEY, strategy_id)
            except Exception:
                pass
        await self._broadcast_state_change("strategy_paused", {"strategy_id": strategy_id})
        await emit("control.strategy_paused", "strategy", strategy_id, {})
        logger.info("control_strategy_paused", strategy_id=strategy_id)

    async def resume_strategy(self, strategy_id: str):
        self._local_paused_strategies.discard(strategy_id)
        r = await self._redis_or(None)
        if r is not None:
            try:
                await r.srem(PAUSED_STRATEGIES_KEY, strategy_id)
            except Exception:
                pass
        await self._broadcast_state_change("strategy_resumed", {"strategy_id": strategy_id})
        logger.info("control_strategy_resumed", strategy_id=strategy_id)

    async def get_paused_strategies(self) -> list[str]:
        result = set(self._local_paused_strategies)
        r = await self._redis_or(None)
        if r is not None:
            try:
                members = await r.smembers(PAUSED_STRATEGIES_KEY)
                for m in members:
                    result.add(m.decode() if isinstance(m, bytes) else str(m))
            except Exception:
                pass
        return sorted(result)

    async def is_market_paused(self, market_id: str) -> bool:
        if market_id in self._local_paused_markets:
            return True
        r = await self._redis_or(None)
        if r is None:
            return False
        try:
            member = await r.sismember(PAUSED_MARKETS_KEY, market_id)
            return bool(member)
        except Exception:
            return False

    async def pause_market(self, market_id: str):
        self._local_paused_markets.add(market_id)
        r = await self._redis_or(None)
        if r is not None:
            try:
                await r.sadd(PAUSED_MARKETS_KEY, market_id)
            except Exception:
                pass
        await self._broadcast_state_change("market_paused", {"market_id": market_id})

    async def resume_market(self, market_id: str):
        self._local_paused_markets.discard(market_id)
        r = await self._redis_or(None)
        if r is not None:
            try:
                await r.srem(PAUSED_MARKETS_KEY, market_id)
            except Exception:
                pass
        await self._broadcast_state_change("market_resumed", {"market_id": market_id})

    async def get_paused_markets(self) -> list[str]:
        result = set(self._local_paused_markets)
        r = await self._redis_or(None)
        if r is not None:
            try:
                members = await r.smembers(PAUSED_MARKETS_KEY)
                for m in members:
                    result.add(m.decode() if isinstance(m, bytes) else str(m))
            except Exception:
                pass
        return sorted(result)

    async def get_state(self) -> dict[str, Any]:
        return {
            "trading_enabled": await self.is_trading_enabled(),
            "execution_mode": await self.get_execution_mode(),
            "paused_strategies": await self.get_paused_strategies(),
            "paused_markets": await self.get_paused_markets(),
        }

    async def _broadcast_state_change(self, event_type: str, payload: dict):
        event = {
            "event_id": f"control:{event_type}:{datetime.now(timezone.utc).isoformat()}",
            "event_type": event_type,
            "entity_type": "control",
            "entity_id": "system",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        await manager.broadcast_event(event, channels=["control", "monitoring"])


control_plane = ControlPlane()
