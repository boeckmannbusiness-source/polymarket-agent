from abc import ABC, abstractmethod
from typing import Any

from app.core.events import EventBus
from app.core.logging import logger


class BaseIngester(ABC):
    name: str = "base"

    def __init__(self):
        self.running = False

    @abstractmethod
    async def run(self):
        ...

    @abstractmethod
    async def stop(self):
        ...

    async def publish_event(self, event_type: str, data: dict):
        await EventBus.publish("market:data", event_type, self.name, data)
        logger.debug("event_published", ingester=self.name, event_type=event_type)
