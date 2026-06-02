from decimal import Decimal
from typing import Any

import httpx

from app.config import settings
from app.exchanges.polymarket_signer import (
    build_clob_headers,
    build_clob_order_payload,
    sign_clob_order,
    get_signer_address,
)
from app.core.logging import logger


CLOB_BASE = settings.POLYMARKET_CLOB_API_URL.rstrip("/")


class PolymarketClobClient:
    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=CLOB_BASE, timeout=30)

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def post_order(
        self,
        token_id: str,
        side: str,
        size: Decimal,
        price: Decimal,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        await self._ensure_client()
        maker_address = get_signer_address()
        if not maker_address:
            raise RuntimeError("POLYMARKET_ETH_PRIVATE_KEY not set")

        order_data = build_clob_order_payload(
            token_id=token_id,
            side=side,
            size=size,
            price=price,
            maker_address=maker_address,
        )
        signature = sign_clob_order(order_data)
        if not signature:
            raise RuntimeError("Failed to sign order")

        payload = {
            "order": order_data,
            "signature": signature,
            "owner": maker_address,
            "side": side.upper(),
            "price": str(price),
            "size": str(size),
        }
        if idempotency_key:
            payload["idempotencyKey"] = idempotency_key

        headers = build_clob_headers(method="POST", request_path="/order")
        try:
            resp = await self._client.post("/order", json=payload, headers=headers)
            resp.raise_for_status()
            result = resp.json()
            logger.info("clob_order_submitted", token_id=token_id, side=side, size=size, price=price)
            return result
        except httpx.HTTPStatusError as e:
            body = e.response.text[:500]
            logger.error("clob_order_failed", status=e.response.status_code, body=body)
            raise RuntimeError(f"CLOB order failed: {e.response.status_code} {body}")
        except httpx.RequestError as e:
            logger.error("clob_order_request_error", error=str(e))
            raise RuntimeError(f"CLOB request error: {e}")

    async def cancel_order(self, order_id: str) -> dict[str, Any]:
        await self._ensure_client()
        headers = build_clob_headers(method="DELETE", request_path=f"/order/{order_id}")
        try:
            resp = await self._client.delete(f"/order/{order_id}", headers=headers)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("clob_cancel_failed", order_id=order_id, status=e.response.status_code)
            raise RuntimeError(f"CLOB cancel failed: {e.response.status_code}")

    async def get_order(self, order_id: str) -> dict[str, Any]:
        await self._ensure_client()
        headers = build_clob_headers(method="GET", request_path=f"/order/{order_id}")
        try:
            resp = await self._client.get(f"/order/{order_id}", headers=headers)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("clob_get_order_failed", order_id=order_id, status=e.response.status_code)
            raise RuntimeError(f"CLOB get order failed: {e.response.status_code}")

    async def get_fills(self, order_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        await self._ensure_client()
        params: dict[str, Any] = {"limit": limit}
        if order_id:
            params["order_id"] = order_id
        headers = build_clob_headers(method="GET", request_path="/data/fills")
        try:
            resp = await self._client.get("/data/fills", params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("clob_get_fills_failed", status=e.response.status_code)
            raise RuntimeError(f"CLOB get fills failed: {e.response.status_code}")

    async def get_market(self, asset_id: str) -> dict[str, Any]:
        await self._ensure_client()
        headers = build_clob_headers(method="GET", request_path=f"/markets/{asset_id}")
        try:
            resp = await self._client.get(f"/markets/{asset_id}", headers=headers)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("clob_get_market_failed", asset_id=asset_id, status=e.response.status_code)
            raise RuntimeError(f"CLOB get market failed: {e.response.status_code}")
