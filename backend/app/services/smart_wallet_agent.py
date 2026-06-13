import json
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.smart_wallet_repository import SmartWalletRepository


class SmartWalletAgent:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.wallet_repo = SmartWalletRepository(db)

    async def handle_trade_event(self, event_data: dict) -> None:
        wallet_address = event_data.get("wallet_address")
        if not wallet_address:
            return

        wallet = await self.wallet_repo.get_by_address(wallet_address)
        if not wallet:
            return

        await self.wallet_repo.update_metrics(
            wallet_id=wallet.id,
            total_trades=wallet.total_trades + 1,
            last_seen_at=datetime.now(timezone.utc),
        )
