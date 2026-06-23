from app.domain.solana.models import SimulationReceipt, SimulationInvalidationError, SimulationInvalidationReason


class SimulationValidator:
    """Validator for simulation receipts, checking for TTL and slot drift."""

    @staticmethod
    def validate(receipt: SimulationReceipt, current_slot: int, drift_threshold: int = 10):
        """Validates a simulation receipt against the current chain state.

        Args:
            receipt: The simulation receipt to validate.
            current_slot: The current slot of the blockchain.
            drift_threshold: Max allowed difference between current slot and simulated slot.
        """
        # 1. TTL Check
        if current_slot > receipt.expires_at_slot:
            raise SimulationInvalidationError(
                SimulationInvalidationReason.TTL_EXPIRED,
                f"Simulation expired: current slot {current_slot} > expires at {receipt.expires_at_slot}"
            )

        # 2. Slot Drift Detection
        slot_delta = abs(current_slot - receipt.slot)
        if slot_delta > drift_threshold:
            raise SimulationInvalidationError(
                SimulationInvalidationReason.SLOT_DRIFT,
                f"Slot drift detected: delta {slot_delta} > threshold {drift_threshold}"
            )

        return True
