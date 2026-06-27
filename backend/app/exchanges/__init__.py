from app.exchanges.base import BaseExchangeAdapter
from app.exchanges.paper import PaperExchangeAdapter


class ExchangeAdapterRegistry:
    _adapters: dict[str, type[BaseExchangeAdapter]] = {}
    _metadata: dict[str, dict] = {}
    _frozen: bool = False

    @classmethod
    def register(cls, engine_type: str, adapter_cls: type[BaseExchangeAdapter], metadata: dict | None = None) -> None:
        if cls._frozen:
            raise PermissionError("ExchangeAdapterRegistry is frozen. Runtime registration is forbidden.")
        cls._adapters[engine_type] = adapter_cls
        cls._metadata[engine_type] = metadata or {"enabled": True, "sandbox_allowed": True}

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
ExchangeAdapterRegistry.register("paper", PaperExchangeAdapter, metadata={
    "enabled": True,
    "sandbox_allowed": True,
    "description": "In-memory paper trading adapter"
})

# Polymarket adapter is registered separately (imported only when needed)
# to avoid hard dependency. Registration happens at module level in
# polymarket_live.py when that module is imported.

# Jupiter simulated adapter — consumes TransactionPlan, produces simulated ExecutionResult
# NO real swaps, NO signing, NO blockchain interaction
from app.exchanges.adapters.jupiter_execution_adapter import JupiterExecutionAdapter
ExchangeAdapterRegistry.register("live_jupiter", JupiterExecutionAdapter, metadata={
    "enabled": True,
    "sandbox_allowed": True,
    "description": "Simulated Jupiter execution for Solana"
})

# Register 'live' for legacy tests compatibility
# This maps to paper by default in tests but allows validation to pass
ExchangeAdapterRegistry.register("live", PaperExchangeAdapter, metadata={
    "enabled": False,
    "sandbox_allowed": False,
    "description": "Legacy live placeholder (Disabled)"
})
