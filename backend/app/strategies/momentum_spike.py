from app.strategies.base import BaseStrategy, StrategyConfig
from app.strategies.signal import StructuredSignal


class MomentumSpikeStrategy(BaseStrategy):
    name = "momentum_spike"
    version = "1.0.0"
    description = "Detects rapid odds movements that may indicate momentum-driven price action"

    async def generate_signal(self, market_state: dict) -> StructuredSignal | None:
        return None
