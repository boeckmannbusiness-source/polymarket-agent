from typing import List, Optional, Dict
from decimal import Decimal
import time

from app.domain.wallet.models import WalletIdentity, WalletBalance
from app.services.wallet.interfaces import WalletProvider, Signer
from app.services.execution.governance.execution_governor import ExecutionGovernor


class MemoryWalletProvider(WalletProvider):
    def __init__(self, initial_wallets: Optional[List[WalletIdentity]] = None):
        self._wallets: Dict[str, WalletIdentity] = {w.address: w for w in (initial_wallets or [])}
        self._balances: Dict[str, Dict[str, Decimal]] = {}

    async def get_wallet(self, address: str) -> Optional[WalletIdentity]:
        return self._wallets.get(address)

    async def list_wallets(self, venue: Optional[str] = None) -> List[WalletIdentity]:
        if venue:
            return [w for w in self._wallets.values() if w.venue == venue]
        return list(self._wallets.values())

    async def get_balance(self, address: str, asset_symbol: str) -> WalletBalance:
        amount = self._balances.get(address, {}).get(asset_symbol, Decimal("0"))
        return WalletBalance(
            address=address,
            asset_symbol=asset_symbol,
            amount=amount,
            last_updated=time.time()
        )

    def set_balance(self, address: str, asset_symbol: str, amount: Decimal):
        if address not in self._balances:
            self._balances[address] = {}
        self._balances[address][asset_symbol] = amount


class NullSigner(Signer):
    """Signer that performs no real signing.
    Required for Sprint 2.0 (No Private Keys).
    """
    def __init__(self, governor: Optional[ExecutionGovernor] = None):
        self._governor = governor

    async def sign(self, payload: str, wallet_address: str) -> str:
        if self._governor:
            self._governor.authorize_sign({"wallet_address": wallet_address})
        # Return a synthetic signature
        return f"null_sig_{wallet_address}_{len(payload)}"
