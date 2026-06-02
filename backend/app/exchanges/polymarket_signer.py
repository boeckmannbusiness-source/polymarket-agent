import uuid
import time
from decimal import Decimal
from typing import Any

from eth_account import Account
from eth_account.messages import encode_typed_data
from web3 import Web3

from app.config import settings
from app.core.logging import logger


CTF_EXCHANGE_EIP712_DOMAIN = {
    "name": "CTF Exchange",
    "version": "1",
    "chainId": settings.POLYGON_CHAIN_ID,
    "verifyingContract": settings.CTF_EXCHANGE_ADDRESS,
}

CTF_EXCHANGE_ORDER_TYPES = {
    "Order": [
        {"name": "salt", "type": "uint256"},
        {"name": "maker", "type": "address"},
        {"name": "signer", "type": "address"},
        {"name": "taker", "type": "address"},
        {"name": "tokenId", "type": "uint256"},
        {"name": "makerAmount", "type": "uint256"},
        {"name": "takerAmount", "type": "uint256"},
        {"name": "expiration", "type": "uint256"},
        {"name": "nonce", "type": "uint256"},
        {"name": "feeRateBps", "type": "uint256"},
        {"name": "side", "type": "uint8"},
        {"name": "signatureType", "type": "uint8"},
    ]
}


def get_signer_address() -> str | None:
    pk = settings.POLYMARKET_ETH_PRIVATE_KEY
    if not pk:
        return None
    acct = Account.from_key(pk)
    return acct.address


def sign_clob_l1_auth(timestamp: int, method: str = "GET", request_path: str = "") -> str | None:
    pk = settings.POLYMARKET_ETH_PRIVATE_KEY
    if not pk:
        return None
    acct = Account.from_key(pk)
    payload = f"{timestamp}{method}{request_path}"
    signed = acct.sign_text(payload)
    return signed.signature.hex()


def build_clob_order_payload(
    token_id: str,
    side: str,
    size: Decimal,
    price: Decimal,
    maker_address: str,
    nonce: int | None = None,
    expiration: int | None = None,
    fee_rate_bps: int = 0,
) -> dict[str, Any]:
    salt = int(uuid.uuid4().hex[:16], 16)
    maker_amount = int(size * Decimal(10**6))
    taker_amount = int(size * price * Decimal(10**6))

    order_data = {
        "salt": salt,
        "maker": maker_address,
        "signer": maker_address,
        "taker": "0x0000000000000000000000000000000000000000",
        "tokenId": token_id,
        "makerAmount": str(maker_amount),
        "takerAmount": str(taker_amount),
        "expiration": str(expiration or (int(time.time()) + 3600)),
        "nonce": str(nonce or 0),
        "feeRateBps": str(fee_rate_bps),
        "side": 0 if side == "buy" else 1,
        "signatureType": 0,
    }
    return order_data


def sign_clob_order(order_data: dict[str, Any]) -> str | None:
    pk = settings.POLYMARKET_ETH_PRIVATE_KEY
    if not pk:
        return None

    typed_data = {
        "domain": CTF_EXCHANGE_EIP712_DOMAIN,
        "types": CTF_EXCHANGE_ORDER_TYPES,
        "primaryType": "Order",
        "message": order_data,
    }
    encoded = encode_typed_data(typed_data)
    acct = Account.from_key(pk)
    signed = acct.sign_message(encoded)
    return signed.signature.hex()


def build_clob_headers(method: str = "GET", request_path: str = "") -> dict[str, str]:
    api_key = settings.POLYMARKET_API_KEY
    secret = settings.POLYMARKET_SECRET
    passphrase = settings.POLYMARKET_PASSPHRASE

    timestamp = int(time.time() * 1000)
    sign_payload = f"{timestamp}{method}{request_path}"
    acct = Account.from_key(secret) if secret else None
    signature = acct.sign_text(sign_payload).signature.hex() if acct else ""

    headers = {
        "POLY_API_KEY": api_key or "",
        "POLY_SIGNATURE": signature,
        "POLY_TIMESTAMP": str(timestamp),
        "POLY_PASSPHRASE": passphrase or "",
        "Content-Type": "application/json",
    }
    return headers
