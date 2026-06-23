from typing import Optional, Any
import httpx
from app.services.rpc.interfaces import RpcReader, RpcHealth, RpcRateLimiter


class SolanaRpcReader(RpcReader, RpcHealth, RpcRateLimiter):
    """Real Solana RPC Read Layer.
    Strictly read-only. Fails closed.
    """
    def __init__(self, endpoint: str, api_key: Optional[str] = None):
        self.endpoint = endpoint
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=10.0)

    async def get_balance(self, address: str) -> int:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [address]
        }
        response = await self._post(payload)
        return response.get("result", {}).get("value", 0)

    async def get_latest_blockhash(self) -> str:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getLatestBlockhash",
            "params": []
        }
        response = await self._post(payload)
        return response.get("result", {}).get("value", {}).get("blockhash", "")

    async def get_token_accounts(self, owner_address: str) -> list[dict]:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTokenAccountsByOwner",
            "params": [
                owner_address,
                {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                {"encoding": "jsonParsed"}
            ]
        }
        response = await self._post(payload)
        return response.get("result", {}).get("value", [])

    async def get_account_info(self, address: str) -> Optional[dict]:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getAccountInfo",
            "params": [address, {"encoding": "jsonParsed"}]
        }
        response = await self._post(payload)
        return response.get("result", {}).get("value")

    async def is_healthy(self) -> bool:
        try:
            payload = {"jsonrpc": "2.0", "id": 1, "method": "getHealth", "params": []}
            response = await self._post(payload)
            return response.get("result") == "ok"
        except Exception:
            return False

    async def check_limit(self) -> bool:
        # Simple placeholder for rate limiting logic
        return True

    async def _post(self, payload: dict) -> dict:
        """Internal POST helper. Fails closed on any error."""
        try:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["X-API-KEY"] = self.api_key

            # Forbidden methods check (extra safety)
            forbidden = {"sendTransaction", "sendRawTransaction", "confirmTransaction"}
            if payload.get("method") in forbidden:
                raise PermissionError(f"Method {payload.get('method')} is forbidden in RpcReader")

            response = await self.client.post(self.endpoint, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            # Log error here if logger available
            # For now, we return empty structure or raise to fail closed
            raise RuntimeError(f"RPC call failed: {str(e)}") from e
