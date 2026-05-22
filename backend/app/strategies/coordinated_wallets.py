from app.strategies.base import BaseStrategy, StrategyConfig
from app.strategies.signal import StructuredSignal


class CoordinatedWalletsStrategy(BaseStrategy):
    name = "coordinated_wallets"
    version = "1.0.0"
    description = "Detects clusters of wallets acting in coordination on the same markets"

    async def generate_signal(self, market_state: dict) -> StructuredSignal | None:
        return None
