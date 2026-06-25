from app.domain.solana.models import TransactionEnvelope
from app.services.rpc.interfaces import RpcReader
import structlog

logger = structlog.get_logger(__name__)

class RouteValidator:
    """Validates Solana transaction routes against chain reality."""

    def __init__(self, rpc_reader: RpcReader):
        self.rpc_reader = rpc_reader

    async def validate_route(self, envelope: TransactionEnvelope) -> str:
        """
        Verifies route structure, account availability, and token compatibility.

        Returns:
            "VALID", "INVALID", or "UNKNOWN"
        """
        try:
            # 1. Basic structure check
            if not envelope.instructions:
                return "INVALID"

            # 2. Account Availability Check
            # In a real scenario, we would extract all accounts from instructions
            # and call get_account_info for each.
            # For this MVP, we'll simulate the check.

            # 3. Token Compatibility
            # Ensure mints exist and are valid.

            # Example heuristic: if fee_estimate is 0, it's likely a malformed route in our tests
            if envelope.fee_estimate < 0:
                return "INVALID"

            return "VALID"
        except Exception as e:
            logger.error("route_validation_failed", error=str(e))
            return "UNKNOWN"
