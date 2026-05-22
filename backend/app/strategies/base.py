from abc import ABC, abstractmethod

from pydantic import BaseModel

from app.strategies.signal import StructuredSignal


class StrategyConfig(BaseModel):
    enabled: bool = True
    min_confidence: float = 0.1
    max_confidence: float = 1.0
    cooldown_seconds: int = 60
    max_signals_per_hour: int = 10


class BaseStrategy(ABC):
    name: str = "base"
    version: str = "0.1.0"
    description: str = ""

    def __init__(self, config: dict | None = None):
        self.config = StrategyConfig(**(config or {}))

    @abstractmethod
    async def generate_signal(self, market_state: dict) -> StructuredSignal | None:
        pass

    async def warmup(self):
        pass

    async def cooldown(self):
        pass

    def get_metadata(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "config": self.config.model_dump(),
        }
