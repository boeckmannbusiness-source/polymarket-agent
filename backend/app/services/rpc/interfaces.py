from abc import ABC, abstractmethod
from typing import Any, Optional


class RpcHealth(ABC):
    @abstractmethod
    async def is_healthy(self) -> bool:
        ...


class RpcRateLimiter(ABC):
    @abstractmethod
    async def check_limit(self) -> bool:
        ...


class RpcReader(ABC):
    @abstractmethod
    async def get_balance(self, address: str) -> int:
        ...

    @abstractmethod
    async def get_latest_blockhash(self) -> str:
        ...

    @abstractmethod
    async def get_token_accounts(self, owner_address: str) -> list[dict]:
        ...

    @abstractmethod
    async def get_account_info(self, address: str) -> Optional[dict]:
        ...

    @abstractmethod
    async def simulate_transaction(self, transaction_b64: str) -> dict:
        ...


class RpcWriter(ABC):
    @abstractmethod
    async def send_transaction(self, transaction_b64: str) -> str:
        ...
