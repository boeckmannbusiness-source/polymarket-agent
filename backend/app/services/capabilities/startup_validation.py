from app.exchanges import ExchangeAdapterRegistry
from app.domain.capabilities import VenueCapability
from .capability_registry import capability_registry, CapabilityRegistrationError
from .capability_validator import CapabilityValidator


def validate_registry_integrity():
    # Symmetry check: Every adapter has capabilities, every capability has an adapter
    # Note: Polymarket adapter registration might be deferred, but let's check what we have
    from app.exchanges import ExchangeAdapterRegistry

    # Get venues from ExchangeAdapterRegistry
    # We need to access private _adapters or add a list method
    adapters = ExchangeAdapterRegistry._adapters.keys()

    for venue in adapters:
        if not capability_registry.has(venue):
            raise CapabilityRegistrationError(f"Venue '{venue}' registered in ExchangeAdapterRegistry but missing in CapabilityRegistry")

    for venue in capability_registry.list_venues():
        if not ExchangeAdapterRegistry.has(venue):
             # Polymarket is a special case mentioned in exchanges/__init__.py
             if venue == "polymarket":
                 continue
             raise CapabilityRegistrationError(f"Venue '{venue}' registered in CapabilityRegistry but missing in ExchangeAdapterRegistry")


def validate_capability_coverage():
    covered = CapabilityValidator.covered_capabilities()
    for cap in VenueCapability:
        # Some capabilities might be purely informational/metadata for now, but 1.8A asks for validation
        if cap not in covered:
            raise CapabilityRegistrationError(f"Capability '{cap}' has no validation logic in CapabilityValidator")


def validate_all():
    validate_registry_integrity()
    validate_capability_coverage()
