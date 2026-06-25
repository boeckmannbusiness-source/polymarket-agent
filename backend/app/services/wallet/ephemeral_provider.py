import secrets
import hashlib
import base64
import base58
from typing import Optional
from app.services.wallet.interfaces import Signer


class EphemeralWalletProvider(Signer):
    """
    Provides ephemeral signing capabilities without persistence.
    Generates runtime keypairs and holds keys in memory only.
    """

    def __init__(self):
        self._keys = {}  # In-memory only: address -> private_key (bytes)

    async def generate_keypair(self) -> str:
        """
        Generates a new Ed25519-style keypair (simulated).
        Returns the public address.
        """
        raw_seed = secrets.token_bytes(32)
        # Simulate a Solana-like address from the seed using base58
        address = base58.b58encode(hashlib.sha256(raw_seed).digest()).decode()

        self._keys[address] = raw_seed
        return address

    async def sign(self, payload: str, wallet_address: str) -> str:
        """
        Signs a payload using the ephemeral key.
        Returns a base64 encoded signature.
        """
        if wallet_address not in self._keys:
            raise ValueError(f"Wallet address {wallet_address} not found in ephemeral provider")

        private_key = self._keys[wallet_address]

        # Simulate signing: HMAC-SHA256 for this sandbox phase
        import hmac
        signature = hmac.new(private_key, payload.encode(), hashlib.sha256).digest()
        return base64.b64encode(signature).decode()

    def destroy(self, wallet_address: str):
        """Removes the key from memory."""
        if wallet_address in self._keys:
            del self._keys[wallet_address]

    def export_private_key(self, wallet_address: str):
        """Forbidden operation."""
        raise PermissionError("Exporting private keys is forbidden in EphemeralWalletProvider")

    def save(self):
        """Forbidden operation."""
        raise PermissionError("Persistence is forbidden in EphemeralWalletProvider")

    def restore(self, *args, **kwargs):
        """Forbidden operation."""
        raise PermissionError("Restoring wallets is forbidden in EphemeralWalletProvider")

    def import_key(self, *args, **kwargs):
        """Forbidden operation."""
        raise PermissionError("Importing keys is forbidden in EphemeralWalletProvider")
