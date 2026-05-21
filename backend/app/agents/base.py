import asyncio
import signal
from abc import ABC, abstractmethod

from app.core.events import EventBus
from app.core.logging import logger
from app.database import async_session_factory
from app.redis import get_redis, close_redis


class BaseAgent(ABC):
    name: str = "base"

    def __init__(self):
        self.running = False
        self._tasks: list[asyncio.Task] = []
        self._stop_event = asyncio.Event()

    @abstractmethod
    async def setup(self):
        ...

    @abstractmethod
    async def loop(self):
        ...

    async def start(self):
        self.running = True
        logger.info("agent_starting", agent=self.name)
        await self.setup()
        await EventBus.publish("agent:event", "agent.started", self.name, {"agent": self.name})
        self._tasks.append(asyncio.create_task(self.loop()))
        self._tasks.append(asyncio.create_task(self._health_check()))

        try:
            await asyncio.gather(*self._tasks)
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    async def stop(self):
        self.running = False
        self._stop_event.set()
        for task in self._tasks:
            task.cancel()
        await close_redis()
        logger.info("agent_stopped", agent=self.name)

    async def _health_check(self):
        while self.running:
            await asyncio.sleep(60)
            await EventBus.publish(
                "agent:event",
                "agent.health",
                self.name,
                {"agent": self.name, "status": "running"},
            )

    async def log_event(self, event_type: str, data: dict | None = None):
        await EventBus.publish("agent:event", event_type, self.name, data or {})
        logger.info("agent_event", agent=self.name, event_type=event_type)

    async def run_forever(self):
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
            except (NotImplementedError, ValueError):
                pass
        await self.start()
