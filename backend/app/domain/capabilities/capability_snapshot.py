from pydantic import BaseModel


class CapabilitySnapshot(BaseModel):
    """Snapshot of system capabilities during execution."""
    execution_mode: str
    rpc_permissions: list[str]
    simulation_enabled: bool
    signing_enabled: bool
    broadcast_enabled: bool
