import json
import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.events import EventBus
from app.redis import get_redis
from app.repositories.smart_wallet_repository import SmartWalletRepository
from app.repositories.wallet_trade_repository import WalletTradeRepository
from app.schemas.helius import HeliusTransaction
from app.services.birdeye_service import BirdeyeEnrichmentService


class HeliusService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.wallet_repo = SmartWalletRepository(db)
        self.trade_repo = WalletTradeRepository(db)
        self.birdeye = BirdeyeEnrichmentService(db)

    async def process_transaction(self, tx: HeliusTransaction, default_wallet: str | None = None) -> int:
        if tx.type != "SWAP":
            return 0

        wallet_address = self._extract_wallet(tx) or default_wallet
        if not wallet_address:
            return 0

        transfers = tx.tokenTransfers
        if not transfers:
            return 0

        wallet = await self._ensure_wallet(wallet_address)
        if not wallet:
            return 0

        mint_address, side, size_usd, price_usd = self._extract_trade(transfers, tx.description)
        if not mint_address or side is None or size_usd is None:
            return 0

        token_amount = transfers[0].token_amount if transfers else None

        existing = await self.trade_repo.get_by_signature(tx.signature)
        if existing:
            return 0

        block_time = datetime.fromtimestamp(tx.timestamp, tz=timezone.utc) if tx.timestamp else datetime.now(timezone.utc)

        trade = await self.trade_repo.create_trade(
            wallet_id=wallet.id,
            tx_signature=tx.signature,
            mint_address=mint_address,
            side=side,
            size_usd=size_usd,
            price_usd=price_usd or 0.0,
            block_time=block_time,
            slot=tx.slot,
        )

        if trade.price_usd == 0.0 and token_amount is not None and token_amount > 0:
            try:
                enriched = await self.birdeye.enrich_trade(trade.id, token_amount=token_amount)
                if enriched:
                    await self.db.refresh(trade)
            except Exception:
                from app.core.logging import logger
                logger.warning("birdeye_enrichment_failed", tx_signature=tx.signature)

        event_payload = {
            "wallet_address": wallet_address,
            "mint_address": mint_address,
            "side": side,
            "size_usd": trade.size_usd,
            "price_usd": trade.price_usd,
            "tx_signature": tx.signature,
            "slot": tx.slot,
            "block_time": block_time.isoformat(),
        }

        try:
            await EventBus.publish(
                "solana:trade:detected",
                "solana:trade:detected",
                "helius_webhook",
                event_payload,
            )
        except Exception:
            from app.core.logging import logger
            logger.critical(
                "eventbus_publish_failed",
                stream="solana:trade:detected",
                tx_signature=tx.signature,
            )
            try:
                r = await get_redis()
                await r.xadd(
                    "solana:dlq:events",
                    {"event_type": "solana:trade:detected", "source": "helius_webhook", "data": json.dumps(event_payload)},
                    maxlen=10000,
                )
            except Exception:
                logger.critical("dlq_push_failed", tx_signature=tx.signature)
        return 1

    async def process_batch(self, transactions: list[HeliusTransaction], default_wallet: str | None = None) -> int:
        count = 0
        for tx in transactions:
            count += await self.process_transaction(tx, default_wallet)
        return count

    def _extract_wallet(self, tx: HeliusTransaction) -> str | None:
        if tx.accounts and len(tx.accounts) > 0:
            return tx.accounts[0]
        return None

    def _extract_trade(
        self,
        transfers: list,
        description: str | None = None,
    ) -> tuple[str | None, str | None, float | None, float | None]:
        mint = transfers[0].mint if transfers else None
        if not mint:
            return None, None, None, None

        side = "buy"
        if description:
            desc_lower = description.lower()
            if "sell" in desc_lower and "sold" in desc_lower:
                side = "sell"
            elif "swap" in desc_lower:
                side = "buy" if " bought " in desc_lower or "buy" in desc_lower.split() else "sell"

        amount = transfers[0].token_amount
        size = amount if amount is not None and amount > 0 else None

        return mint, side, size, None

    async def _ensure_wallet(self, wallet_address: str):
        existing = await self.wallet_repo.get_by_address(wallet_address)
        if existing:
            return existing

        try:
            return await self.wallet_repo.create_wallet(
                wallet_address=wallet_address,
                source="helius_webhook",
                first_seen_at=datetime.now(timezone.utc),
            )
        except IntegrityError:
            await self.db.rollback()
            existing = await self.wallet_repo.get_by_address(wallet_address)
            if existing:
                return existing
            raise
