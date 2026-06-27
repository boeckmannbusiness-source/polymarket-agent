import pytest
from app.exchanges import ExchangeAdapterRegistry
from app.exchanges.base import BaseExchangeAdapter

def test_registry_immutable_after_startup():
    """Prove that ExchangeAdapterRegistry cannot be modified after freeze()."""
    # Registry should be frozen in main.py, but for unit test let's ensure it.
    ExchangeAdapterRegistry.freeze()

    class MockAdapter(BaseExchangeAdapter):
        async def submit_order(self, order): pass
        async def get_order_status(self, order_id): pass
        async def cancel_order(self, order_id): pass

    with pytest.raises(PermissionError) as excinfo:
        ExchangeAdapterRegistry.register("rogue_adapter", MockAdapter)

    assert "ExchangeAdapterRegistry is frozen" in str(excinfo.value)
