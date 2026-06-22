from app.services.rpc.interfaces import RpcWriter
from app.services.execution.governance.execution_governor import ExecutionAuthorizationError


class NullRpcWriter(RpcWriter):
    """RPC Writer that forbids all operations.
    Used for DISABLED or SIMULATION modes.
    """
    async def simulate_transaction(self, transaction_b64: str) -> dict:
        raise ExecutionAuthorizationError("RPC simulation forbidden in current mode")

    async def send_transaction(self, transaction_b64: str) -> str:
        raise ExecutionAuthorizationError("RPC write forbidden in current mode")
