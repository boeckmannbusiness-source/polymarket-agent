import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.research_trade_repository import ResearchTradeRepository
from app.repositories.smart_wallet_repository import SmartWalletRepository
from app.repositories.wallet_trade_repository import WalletTradeRepository


_SIGNAL_ID_COUNTER: int = 0


def _make_signal_id() -> str:
    global _SIGNAL_ID_COUNTER
    _SIGNAL_ID_COUNTER += 1
    import hashlib
    raw = f"solana-{datetime.now(timezone.utc).isoformat()}-{_SIGNAL_ID_COUNTER}"
    h = hashlib.sha256(raw.encode()).hexdigest()[:22]
    return f"sig_{h}"


class SignalSeedService:
    HIGH_SCORE_THRESHOLD: float = 0.7
    VELOCITY_MIN_TRADES: int = 3
    VELOCITY_MIN_WALLETS: int = 2
    VELOCITY_WINDOW_MINUTES: int = 5

    def __init__(self, db: AsyncSession):
        self.db = db
        self.wallet_repo = SmartWalletRepository(db)
        self.trade_repo = WalletTradeRepository(db)
        self.research_repo = ResearchTradeRepository(db)

    async def evaluate_trade_event(self, event_data: dict) -> int:
        wallet_address = event_data.get("wallet_address")
        mint_address = event_data.get("mint_address")
        price_usd = event_data.get("price_usd", 0) or 0
        trade_id_str = event_data.get("trade_id")

        if not wallet_address or not mint_address:
            return 0

        if price_usd <= 0:
            return 0

        wallet_trade_id: uuid.UUID | None = None
        if trade_id_str:
            try:
                wallet_trade_id = uuid.UUID(trade_id_str)
            except (ValueError, AttributeError):
                pass

        wallet = await self.wallet_repo.get_by_address(wallet_address)
        if not wallet:
            return 0

        count = 0

        if float(wallet.score) >= self.HIGH_SCORE_THRESHOLD:
            confidence = min(float(wallet.score), 0.95)
            await self._seed_signal(
                strategy="high_score_entry",
                confidence=round(confidence, 6),
                entry_price=price_usd,
                wallet_trade_id=wallet_trade_id,
                signal_id=_make_signal_id(),
            )
            count += 1

        recent = await self.trade_repo.list_for_mint(
            mint_address, limit=self.VELOCITY_MIN_TRADES,
        )
        if len(recent) >= self.VELOCITY_MIN_TRADES:
            unique_wallets = set(t.wallet_id for t in recent)
            if len(unique_wallets) >= self.VELOCITY_MIN_WALLETS:
                await self._seed_signal(
                    strategy="token_velocity_spike",
                    confidence=0.6,
                    entry_price=price_usd,
                    wallet_trade_id=wallet_trade_id,
                    signal_id=_make_signal_id(),
                )
                count += 1

        return count

    async def _seed_signal(
        self,
        strategy: str,
        confidence: float,
        entry_price: float,
        wallet_trade_id: uuid.UUID | None,
        signal_id: str,
    ) -> None:
        await self.research_repo.create_trade(
            strategy=strategy,
            entry_price=entry_price,
            opened_at=datetime.now(timezone.utc),
            signal_id=signal_id,
            wallet_trade_id=wallet_trade_id,
            confidence=confidence,
        )
