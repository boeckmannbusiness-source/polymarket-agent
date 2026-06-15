from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.research_trade import ResearchTrade
from app.models.shadow_position import ShadowPosition
from app.models.smart_wallet import SmartWallet
from app.models.wallet_trade import SolanaWalletTrade


class ShadowAnalyticsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_stats(self) -> dict:
        result = await self.db.execute(
            select(
                func.count(func.distinct(ShadowPosition.research_trade_id)).label("total_signals"),
                func.sum(case((ShadowPosition.status == "open", 1), else_=0)).label("open_positions"),
                func.sum(case((ShadowPosition.status == "closed", 1), else_=0)).label("closed_positions"),
            ),
        )
        counts = result.one()

        result2 = await self.db.execute(
            select(
                func.sum(ShadowPosition.net_pnl_usd).label("total_net_pnl"),
                func.sum(ShadowPosition.size_usd).label("total_size"),
                func.sum(
                    case((ShadowPosition.net_pnl_usd > 0, ShadowPosition.net_pnl_usd), else_=0),
                ).label("sum_winners"),
                func.sum(
                    case((ShadowPosition.net_pnl_usd < 0, ShadowPosition.net_pnl_usd), else_=0),
                ).label("sum_losers"),
                func.sum(case((ShadowPosition.net_pnl_usd > 0, 1), else_=0)).label("win_count"),
                func.count(ShadowPosition.id).label("closed_count"),
            ).where(
                ShadowPosition.status == "closed",
                ShadowPosition.net_pnl_usd.isnot(None),
            ),
        )
        a = result2.one()

        total_net = _to_float(a.total_net_pnl) or 0.0
        total_sz = _to_float(a.total_size) or 0.0
        sum_w = _to_float(a.sum_winners) or 0.0
        sum_l = _to_float(a.sum_losers) or 0.0
        wc = a.win_count or 0
        cc = a.closed_count or 0

        roi = (total_net / total_sz * 100.0) if total_sz else 0.0
        pf = (sum_w / abs(sum_l)) if sum_l else None
        wr = (wc / cc * 100.0) if cc else 0.0

        return {
            "total_signals": counts.total_signals or 0,
            "open_positions": counts.open_positions or 0,
            "closed_positions": counts.closed_positions or 0,
            "net_roi_pct": round(roi, 2),
            "profit_factor": round(pf, 4) if pf is not None else None,
            "win_rate_pct": round(wr, 2),
        }

    async def get_performance(self) -> list[dict]:
        result = await self.db.execute(
            select(
                ShadowPosition.strategy,
                func.count(ShadowPosition.id).label("positions"),
                func.sum(case((ShadowPosition.net_pnl_usd > 0, 1), else_=0)).label("win_count"),
                func.count(ShadowPosition.id).label("total_closed"),
                func.avg(
                    ShadowPosition.net_pnl_usd / func.nullif(ShadowPosition.size_usd, 0),
                ).label("avg_return"),
                func.sum(ShadowPosition.net_pnl_usd).label("net_pnl_usd"),
            ).where(
                ShadowPosition.status == "closed",
                ShadowPosition.net_pnl_usd.isnot(None),
            ).group_by(ShadowPosition.strategy)
            .order_by(
                func.sum(ShadowPosition.net_pnl_usd).desc(),
                ShadowPosition.strategy.asc(),
            ),
        )
        rows = result.all()
        return [
            {
                "strategy": r.strategy,
                "positions": r.positions or 0,
                "win_rate_pct": round(
                    (r.win_count / r.total_closed * 100.0) if r.total_closed else 0.0, 2,
                ),
                "avg_return_pct": round(
                    (float(r.avg_return) * 100.0) if r.avg_return is not None else 0.0, 4,
                ),
                "net_pnl_usd": round(_to_float(r.net_pnl_usd) or 0.0, 2),
            }
            for r in rows
        ]

    async def get_concentration(self) -> dict:
        result = await self.db.execute(
            select(
                SmartWallet.wallet_address,
                func.sum(ShadowPosition.net_pnl_usd).label("net_pnl"),
            ).select_from(ShadowPosition)
            .join(ResearchTrade, ResearchTrade.id == ShadowPosition.research_trade_id)
            .join(SolanaWalletTrade, SolanaWalletTrade.id == ResearchTrade.wallet_trade_id)
            .join(SmartWallet, SmartWallet.id == SolanaWalletTrade.wallet_id)
            .where(ShadowPosition.status == "closed")
            .where(ShadowPosition.net_pnl_usd.isnot(None))
            .where(ShadowPosition.net_pnl_usd > 0)
            .group_by(SmartWallet.wallet_address)
            .order_by(func.sum(ShadowPosition.net_pnl_usd).desc()),
        )
        rows = result.all()
        wallet_pnls = [(_to_float(r.net_pnl) or 0.0) for r in rows]
        total_positive = sum(wallet_pnls)

        if total_positive <= 0:
            return {"top_wallet_share_pct": None, "top_5_wallet_share_pct": None}

        top = wallet_pnls[0] if wallet_pnls else 0.0
        top5 = sum(wallet_pnls[:5])

        return {
            "top_wallet_share_pct": round(
                max(0.0, min(100.0, top / total_positive * 100.0)), 2,
            ),
            "top_5_wallet_share_pct": round(
                max(0.0, min(100.0, top5 / total_positive * 100.0)), 2,
            ),
        }

    async def get_wallet_universe(self) -> dict:
        result = await self.db.execute(
            select(
                SmartWallet.wallet_address,
                func.sum(ShadowPosition.net_pnl_usd).label("pnl"),
                func.sum(case((ShadowPosition.net_pnl_usd > 0, 1), else_=0)).label("wins"),
                func.count(ShadowPosition.id).label("total"),
            ).select_from(ShadowPosition)
            .join(ResearchTrade, ResearchTrade.id == ShadowPosition.research_trade_id)
            .join(SolanaWalletTrade, SolanaWalletTrade.id == ResearchTrade.wallet_trade_id)
            .join(SmartWallet, SmartWallet.id == SolanaWalletTrade.wallet_id)
            .where(ShadowPosition.status == "closed")
            .where(ShadowPosition.net_pnl_usd.isnot(None))
            .group_by(SmartWallet.wallet_address)
            .order_by(
                func.sum(ShadowPosition.net_pnl_usd).desc(),
                SmartWallet.wallet_address.asc(),
            ),
        )
        wallet_rows = result.all()

        observed = len(wallet_rows)
        active = sum(1 for r in wallet_rows if (r.wins or 0) + (r.total or 0) > 0)

        top_wallets = [
            {
                "wallet": r.wallet_address,
                "pnl": round(_to_float(r.pnl) or 0.0, 2),
                "win_rate": round(
                    ((r.wins or 0) / (r.total or 1) * 100.0) if (r.total or 0) > 0 else 0.0, 2,
                ),
            }
            for r in wallet_rows[:10]
        ]

        return {
            "observed_wallets": observed,
            "active_wallets": active,
            "activation_rate_pct": round(
                (active / observed * 100.0) if observed else 0.0, 2,
            ),
            "top_wallets": top_wallets,
        }


def _to_float(val: Decimal | float | None) -> float | None:
    if val is None:
        return None
    return float(val)
