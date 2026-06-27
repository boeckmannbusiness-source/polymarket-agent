from app.config import settings
from app.core.exceptions import StartupSafetyViolation
from app.core.logging import logger
from app.exchanges import ExchangeAdapterRegistry
from app.domain.capabilities import VenueCapability
from .capability_registry import capability_registry, CapabilityRegistrationError
from .capability_validator import CapabilityValidator


class StartupSafetyValidator:
    """
    Enforces structural safety invariants at process boot.
    No warning mode. No auto-fix. No fallback.
    """

    @staticmethod
    def validate():
        logger.info("startup_safety_validation_started")

        # 1. EXECUTION_MODE ∈ {SIMULATION, SANDBOX}
        if settings.EXECUTION_MODE not in ["simulation", "sandbox"]:
            logger.critical("startup_safety_violation",
                            field="EXECUTION_MODE",
                            value=settings.EXECUTION_MODE,
                            allowed=["simulation", "sandbox"])
            raise StartupSafetyViolation(
                f"Invalid EXECUTION_MODE: {settings.EXECUTION_MODE}. Must be SIMULATION or SANDBOX."
            )

        # 2. STRICT_LIVE_ENABLED == False
        if settings.STRICT_LIVE_ENABLED is not False:
            logger.critical("startup_safety_violation",
                            field="STRICT_LIVE_ENABLED",
                            value=settings.STRICT_LIVE_ENABLED)
            raise StartupSafetyViolation(
                "STRICT_LIVE_ENABLED must be False for certification closure."
            )

        # 3. CAPITAL_ENABLED == False
        if settings.CAPITAL_ENABLED is not False:
            logger.critical("startup_safety_violation",
                            field="CAPITAL_ENABLED",
                            value=settings.CAPITAL_ENABLED)
            raise StartupSafetyViolation(
                "CAPITAL_ENABLED must be False for certification closure."
            )

        logger.info("startup_safety_validation_passed")


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
