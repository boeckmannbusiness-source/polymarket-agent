from app.strategies.base import BaseStrategy, StrategyConfig
from app.strategies.signal import StructuredSignal
from app.strategies.whale_following import WhaleFollowingStrategy
from app.strategies.early_whale_entry import EarlyWhaleEntryStrategy
from app.strategies.liquidity_vacuum import LiquidityVacuumStrategy
from app.strategies.spread_compression import SpreadCompressionStrategy
from app.strategies.coordinated_wallets import CoordinatedWalletsStrategy
from app.strategies.momentum_spike import MomentumSpikeStrategy
from app.strategies.momentum_reversion import MomentumReversionStrategy
from app.strategies.adaptive_meta import AdaptiveMetaStrategy
from app.strategies.news_repricing import NewsRepricingStrategy
from app.strategies.ensemble import EnsembleStrategy


_registry: dict[str, type[BaseStrategy]] = {}


def register_strategy(strategy_class: type[BaseStrategy]):
    _registry[strategy_class.name] = strategy_class


def get_strategy(name: str, config: dict | None = None) -> BaseStrategy:
    cls = _registry.get(name)
    if cls is None:
        raise ValueError(f"Unknown strategy: {name}. Available: {list(_registry.keys())}")
    return cls(config=config)


def list_strategies() -> list[dict]:
    return [cls(config=None).get_metadata()
            for cls in _registry.values()]


def get_strategy_names() -> list[str]:
    return list(_registry.keys())


for cls in [
    WhaleFollowingStrategy,
    EarlyWhaleEntryStrategy,
    LiquidityVacuumStrategy,
    SpreadCompressionStrategy,
    CoordinatedWalletsStrategy,
    MomentumSpikeStrategy,
    MomentumReversionStrategy,
    AdaptiveMetaStrategy,
    NewsRepricingStrategy,
    EnsembleStrategy,
]:
    register_strategy(cls)


__all__ = [
    "BaseStrategy",
    "StrategyConfig",
    "StructuredSignal",
    "WhaleFollowingStrategy",
    "EarlyWhaleEntryStrategy",
    "LiquidityVacuumStrategy",
    "SpreadCompressionStrategy",
    "CoordinatedWalletsStrategy",
    "MomentumSpikeStrategy",
    "MomentumReversionStrategy",
    "AdaptiveMetaStrategy",
    "NewsRepricingStrategy",
    "EnsembleStrategy",
    "register_strategy",
    "get_strategy",
    "list_strategies",
    "get_strategy_names",
]
