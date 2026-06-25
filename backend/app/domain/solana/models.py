import hashlib
import json
from decimal import Decimal
from enum import Enum
from typing import List, Optional, Any
from pydantic import BaseModel, Field
from app.domain.planning.transaction_instruction import TransactionInstruction


class TransactionPayload(BaseModel):
    """The raw payload to be signed."""
    serialized_payload_b64: str

    def fingerprint(self) -> str:
        """Produces a deterministic fingerprint of the payload."""
        return hashlib.sha256(self.serialized_payload_b64.encode()).hexdigest()


class TransactionEnvelope(BaseModel):
    """Encapsulates a Solana transaction construction."""
    instructions: List[TransactionInstruction]
    payload: TransactionPayload
    slippage_bps: int
    fee_estimate: int  # in lamports
    asset_resolution: Optional[Any] = None  # AssetResolution
    metadata: Optional[dict] = Field(default_factory=dict)

    def fingerprint(self) -> str:
        """Deterministic fingerprint for the entire envelope."""
        components = {
            "payload_fp": self.payload.fingerprint(),
            "slippage": self.slippage_bps,
            "fee": self.fee_estimate,
            "instruction_count": len(self.instructions)
        }
        raw = json.dumps(components, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()


class SimulationInvalidationReason(str, Enum):
    TTL_EXPIRED = "TTL_EXPIRED"
    SLOT_DRIFT = "SLOT_DRIFT"
    CAPABILITY_CHANGED = "CAPABILITY_CHANGED"
    HASH_MISMATCH = "HASH_MISMATCH"


class SimulationInvalidationError(Exception):
    def __init__(self, reason: SimulationInvalidationReason, message: str):
        self.reason = reason
        self.message = message
        super().__init__(f"{reason}: {message}")


class SimulationReceipt(BaseModel):
    """A real receipt from on-chain simulation."""
    success: bool
    compute_units: int
    estimated_fee: int
    logs: List[str]
    slot: int
    blockhash: str
    created_slot: int = 0
    ttl_slots: int = 150
    expires_at_slot: int = 0
    hash: Optional[str] = None

    # Reality Expansion
    simulation_id: str = ""
    account_state_hash: str = ""
    route_metadata: dict = Field(default_factory=dict)
    simulation_hash: Optional[str] = None
    valid_until_slot: int = 0
    compute_delta: int = 0
    fee_snapshot: dict = Field(default_factory=dict)
    route_snapshot: dict = Field(default_factory=dict)
    slippage_snapshot: dict = Field(default_factory=dict)
    wallet_context: dict = Field(default_factory=dict)

    metadata: Optional[dict] = Field(default_factory=dict)

    def calculate_hash(self, tx_message: str) -> str:
        """Produces a deterministic fingerprint of the simulation output."""

        def canonical_serialize(obj):
            if isinstance(obj, Decimal):
                # Normalize decimals: remove trailing zeros and use fixed notation
                normalized = obj.normalize()
                return f"{normalized:f}"
            if isinstance(obj, dict):
                return {k: canonical_serialize(v) for k, v in sorted(obj.items())}
            if isinstance(obj, list):
                return [canonical_serialize(i) for i in obj]
            return obj

        components = {
            "tx_message": tx_message,
            "blockhash": self.blockhash,
            "slot": self.slot,
            "compute_units": self.compute_units,
            "estimated_fee": self.estimated_fee,
            "logs": self.logs,
            "simulation_id": self.simulation_id,
            "account_state_hash": self.account_state_hash,
            "route_metadata": self.route_metadata,
            "valid_until_slot": self.valid_until_slot,
            "compute_delta": self.compute_delta,
            "fee_snapshot": self.fee_snapshot,
            "route_snapshot": self.route_snapshot,
            "slippage_snapshot": self.slippage_snapshot,
            "wallet_context": self.wallet_context,
            "metadata": self.metadata
        }

        # Apply canonical serialization to ensure Decimals and dicts are stable
        canonical_components = canonical_serialize(components)

        # Use sort_keys=True for final JSON stability
        raw = json.dumps(canonical_components, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()


class SimulationSnapshot(BaseModel):
    """Snapshot of a simulation for replay preservation."""
    receipt: SimulationReceipt
    timestamp: float
    rpc_endpoint: str


class TransactionReceipt(BaseModel):
    """A synthetic receipt from simulation."""
    transaction_hash: str  # synthetic for simulation
    success: bool
    estimated_fees: int
    compute_units: int
    execution_trace: Optional[List[str]] = None
    simulation_snapshot: Optional[SimulationSnapshot] = None
    metadata: Optional[dict] = Field(default_factory=dict)
