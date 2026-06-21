from abc import ABC, abstractmethod
from typing import List, Optional
from app.domain.wallet.models import WalletIdentity, WalletBalance


class WalletProvider(ABC):
    @abstractmethod
    async def get_wallet(self, address: str) -> Optional[WalletIdentity]:
        ...

    @abstractmethod
    async def list_wallets(self, venue: Optional[str] = None) -> List[WalletIdentity]:
        ...

    @abstractmethod
    async def get_balance(self, address: str, asset_symbol: str) -> WalletBalance:
        ...


class Signer(ABC):
    @abstractmethod
    async def sign(self, payload: str, wallet_address: str) -> str:
        """Signs a payload. Returns a signature string (Base64 or Hex)."""
        ...
