from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.attribution_service import AttributionService

router = APIRouter(prefix="/attribution", tags=["attribution"])


@router.get("/{signal_outcome_id}")
async def get_attribution(signal_outcome_id: str, db: AsyncSession = Depends(get_db)):
    svc = AttributionService(db)
    att = await svc.get_attribution(signal_outcome_id)
    if att is None:
        return {"status": "not_found"}
    return _att_to_dict(att)


@router.get("/strategy/{strategy_name}")
async def get_strategy_attributions(strategy_name: str, limit: int = 100, db: AsyncSession = Depends(get_db)):
    svc = AttributionService(db)
    attributions = await svc.get_strategy_attributions(strategy_name, limit=limit)
    return {
        "strategy": strategy_name,
        "count": len(attributions),
        "attributions": [_att_to_dict(a) for a in attributions],
    }


def _att_to_dict(att) -> dict:
    return {
        "id": str(att.id),
        "signal_outcome_id": str(att.signal_outcome_id),
        "strategy_name": att.strategy_name,
        "entry_price": float(att.entry_price),
        "entry_momentum_1h": float(att.entry_momentum_1h) if att.entry_momentum_1h is not None else None,
        "entry_volatility_1h": float(att.entry_volatility_1h) if att.entry_volatility_1h is not None else None,
        "entry_spread_ratio": float(att.entry_spread_ratio) if att.entry_spread_ratio is not None else None,
        "entry_regime": att.entry_regime,
        "entry_archetype": att.entry_archetype,
        "total_pnl": float(att.total_pnl) if att.total_pnl is not None else None,
        "momentum_contribution": float(att.momentum_contribution) if att.momentum_contribution is not None else None,
        "whale_contribution": float(att.whale_contribution) if att.whale_contribution is not None else None,
        "spread_contribution": float(att.spread_contribution) if att.spread_contribution is not None else None,
        "volatility_contribution": float(att.volatility_contribution) if att.volatility_contribution is not None else None,
        "liquidity_contribution": float(att.liquidity_contribution) if att.liquidity_contribution is not None else None,
        "residual": float(att.residual) if att.residual is not None else None,
        "checkpoint_attributions": att.checkpoint_attributions,
        "holding_time_seconds": att.holding_time_seconds,
    }
