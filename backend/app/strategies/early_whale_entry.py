from app.strategies.base import BaseStrategy, StrategyConfig
from app.strategies.signal import StructuredSignal


class EarlyWhaleEntryStrategy(BaseStrategy):
    name = "early_whale_entry"
    version = "1.0.0"
    description = "Detects whales entering early positions before significant odds moves"

    async def generate_signal(self, market_state: dict) -> StructuredSignal | None:
        return None
