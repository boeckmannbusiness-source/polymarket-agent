import pytest
from app.exchanges import ExchangeAdapterRegistry
from app.services.capabilities import capability_registry, validate_all, CapabilityRegistrationError

def test_capability_registry_integrity():
    """
    Architecture test: adapter <-> capability symmetry.
    Every adapter must have capabilities.
    Every capability set must have an adapter (except Polymarket special case).
    """
    # This should pass with current setup
    validate_all()

def test_missing_capability_for_adapter():
    """Fail if an adapter exists without registered capabilities."""
    class FakeAdapter: pass
    ExchangeAdapterRegistry.register("missing_caps", FakeAdapter)

    with pytest.raises(CapabilityRegistrationError, match="missing in CapabilityRegistry"):
        validate_all()

    # Cleanup
    del ExchangeAdapterRegistry._adapters["missing_caps"]

def test_missing_adapter_for_capability():
    """Fail if capabilities exist without a registered adapter."""
    from app.domain.capabilities import VenueCapabilities
    capability_registry.register("missing_adapter", VenueCapabilities(venue="missing_adapter", supports=set()))

    with pytest.raises(CapabilityRegistrationError, match="missing in ExchangeAdapterRegistry"):
        validate_all()

    # Cleanup
    del capability_registry._registry["missing_adapter"]
