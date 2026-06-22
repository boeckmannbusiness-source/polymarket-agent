from abc import ABC, abstractmethod
from typing import Any, Optional


class RpcReader(ABC):
    @abstractmethod
    async def get_balance(self, address: str) -> int:
        ...

    @abstractmethod
    async def get_latest_blockhash(self) -> str:
        ...


class RpcWriter(ABC):
    @abstractmethod
    async def simulate_transaction(self, transaction_b64: str) -> dict:
        ...

    @abstractmethod
    async def send_transaction(self, transaction_b64: str) -> str:
        ...
