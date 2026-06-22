from typing import Optional
from app.services.rpc.interfaces import RpcWriter
from app.services.execution.governance.execution_governor import ExecutionAuthorizationError


class SandboxRpcWriter(RpcWriter):
    """RPC Writer that allows simulation but forbids broadcasting.
    Used for SANDBOX mode.
    """
    def __init__(self, real_rpc: Optional[RpcWriter] = None):
        self._real_rpc = real_rpc

    async def simulate_transaction(self, transaction_b64: str) -> dict:
        if self._real_rpc:
            return await self._real_rpc.simulate_transaction(transaction_b64)
        return {"success": True, "logs": ["sandbox_simulation"]}

    async def send_transaction(self, transaction_b64: str) -> str:
        raise ExecutionAuthorizationError("RPC send (broadcast) forbidden in SANDBOX mode")
