from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.shadow_analytics_repository import ShadowAnalyticsRepository
from app.schemas.shadow_validation import (
    ConcentrationResponse,
    StrategyPerformanceResponse,
    TopWalletResponse,
    ValidationStatsResponse,
    WalletUniverseResponse,
)


class ShadowValidationService:
    def __init__(self, db: AsyncSession):
        self.repo = ShadowAnalyticsRepository(db)

    async def get_stats(self) -> ValidationStatsResponse:
        data = await self.repo.get_stats()
        return ValidationStatsResponse(**data)

    async def get_performance(self) -> list[StrategyPerformanceResponse]:
        rows = await self.repo.get_performance()
        return [StrategyPerformanceResponse(**r) for r in rows]

    async def get_concentration(self) -> ConcentrationResponse:
        data = await self.repo.get_concentration()
        return ConcentrationResponse(**data)

    async def get_wallet_universe(self) -> WalletUniverseResponse:
        data = await self.repo.get_wallet_universe()
        return WalletUniverseResponse(**data)
