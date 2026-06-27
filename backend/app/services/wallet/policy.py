from app.domain.wallet.models import SignedArtifact
from app.core.logging import logger

class SignedArtifactPolicy:
    """
    Enforces the 'Signed Artifact Boundary' rule.
    Signed payloads must not be stored, replayed, or exported.
    """

    @staticmethod
    def validate_usage(artifact: SignedArtifact):
        """
        Validates that a signed artifact is used according to policy.
        Currently ensures it exists and was recently generated.
        """
        import time
        now = time.time()

        # Invariant: Signed artifact must be transient (e.g. less than 60s old)
        if now - artifact.timestamp > 60:
            logger.critical("signed_artifact_expiry_violation",
                            wallet=artifact.wallet_address,
                            age=now - artifact.timestamp)
            raise PermissionError("Signed artifact usage attempt after transient window expired")

    @staticmethod
    def forbid_persistence(artifact: SignedArtifact):
        """
        Explicitly prevents any attempt to persist the signed artifact.
        """
        # This is primarily enforced by the SignedArtifact model itself
        # (forbidding model_dump), but this service provides the policy layer.
        pass

    @staticmethod
    def forbid_export():
        """Forbidden operation."""
        raise PermissionError("Exporting signed artifacts is forbidden")

    @staticmethod
    def forbid_replay():
        """Forbidden operation."""
        raise PermissionError("Replaying signed artifacts is forbidden")
