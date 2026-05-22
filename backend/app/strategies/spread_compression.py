from app.strategies.base import BaseStrategy, StrategyConfig
from app.strategies.signal import StructuredSignal


class SpreadCompressionStrategy(BaseStrategy):
    name = "spread_compression"
    version = "1.0.0"
    description = "Detects bid-ask spread narrowing which often precedes large orders or odds moves"

    async def generate_signal(self, market_state: dict) -> StructuredSignal | None:
        return None
