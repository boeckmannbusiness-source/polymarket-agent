from app.exchanges.base import BaseExchangeAdapter
from app.exchanges.paper import PaperExchangeAdapter


class ExchangeAdapterRegistry:
    _adapters: dict[str, type[BaseExchangeAdapter]] = {}
    _frozen: bool = False

    @classmethod
    def register(cls, engine_type: str, adapter_cls: type[BaseExchangeAdapter]) -> None:
        if cls._frozen:
            raise PermissionError("ExchangeAdapterRegistry is frozen. Runtime registration is forbidden.")
        cls._adapters[engine_type] = adapter_cls

    @classmethod
    def freeze(cls) -> None:
        """Freezes the registry to prevent further registrations."""
        cls._frozen = True

    @classmethod
    def get(cls, engine_type: str) -> type[BaseExchangeAdapter] | None:
        return cls._adapters.get(engine_type)

    @classmethod
    def has(cls, engine_type: str) -> bool:
        return engine_type in cls._adapters


# ── Register known adapters ───────────────────────────────────
ExchangeAdapterRegistry.register("paper", PaperExchangeAdapter)

# Polymarket adapter is registered separately (imported only when needed)
# to avoid hard dependency. Registration happens at module level in
# polymarket_live.py when that module is imported.

# Jupiter simulated adapter — consumes TransactionPlan, produces simulated ExecutionResult
# NO real swaps, NO signing, NO blockchain interaction
from app.exchanges.adapters.jupiter_execution_adapter import JupiterExecutionAdapter
ExchangeAdapterRegistry.register("live_jupiter", JupiterExecutionAdapter)

# Register 'live' for legacy tests compatibility
# This maps to paper by default in tests but allows validation to pass
ExchangeAdapterRegistry.register("live", PaperExchangeAdapter)
