from __future__ import annotations
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SignalOutcome, TradeAttribution

if TYPE_CHECKING:
    from app.replay.engine import ReplayedSignal

logger = logging.getLogger(__name__)


class AttributionService:
    """Decomposes signal PnL into factor contributions.

    For each checkpoint window, the total price movement is decomposed into:
      1. momentum_contribution  — price change aligned with entry momentum
      2. whale_contribution     — price impact from large trades during holding
      3. spread_contribution    — impact from spread compression/expansion
      4. volatility_contribution — impact from volatility regime change
      5. liquidity_contribution  — impact from volume/liquidity changes
      6. residual               — unexplained portion
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def decompose(self, outcome: SignalOutcome, entry_features: dict | None = None,
                        checkpoint_snapshots: dict[str, dict] | None = None,
                        entry_price: float | None = None) -> TradeAttribution | None:
        """Compute attribution for a single signal outcome."""
        ef = entry_features or {}
        cs = checkpoint_snapshots or {}

        if entry_price is None or entry_price <= 0:
            entry_price = _float(ef.get("current_price")) or _float(ef.get("entry_price"))
        if entry_price is None or entry_price <= 0:
            return None

        close_price = outcome.probability_close or outcome.probability_4h or outcome.probability_1h
        total_pnl = outcome.pnl_close

        if close_price is None or total_pnl is None:
            return None

        entry_mom = _float(ef.get("momentum_1h"))
        entry_vol = _float(ef.get("volatility_1h")) or _float(ef.get("volatility"))
        entry_spread = _float(ef.get("spread_ratio"))
        entry_volume_5m = _float(ef.get("volume_5m"))
        entry_regime = str(ef.get("regime", "")) or str(ef.get("market_regime", ""))
        entry_whale = _float(ef.get("size"))
        entry_archetype = str(ef.get("archetype", "")) or str(ef.get("market_archetype", "")) or "unknown"

        exit_snap = _best_checkpoint_snapshot(cs)
        exit_mom = _float(exit_snap.get("momentum_1h")) if exit_snap else None
        exit_vol = _float(exit_snap.get("volatility_1h")) or _float(exit_snap.get("volatility")) if exit_snap else None
        exit_spread = _float(exit_snap.get("spread_ratio")) if exit_snap else None
        exit_volume_5m = _float(exit_snap.get("volume_5m")) if exit_snap else None

        direction_sign = 1 if (outcome.signal_direction or "").upper() == "BUY_YES" else -1
        total_move = float(total_pnl) * direction_sign

        if entry_mom is not None and direction_sign == -1:
            adj_mom = -entry_mom
        else:
            adj_mom = entry_mom
        mom_contrib = _compute_momentum_contrib(adj_mom, total_move)
        whale_contrib = _compute_whale_contrib(cs, total_move, outcome.signal_direction or "BUY_YES")
        spread_contrib = _compute_spread_contrib(entry_spread, exit_spread, direction_sign)
        vol_contrib = _compute_volatility_contrib(entry_vol, exit_vol, entry_price)
        liq_contrib = _compute_liquidity_contrib(entry_volume_5m, exit_volume_5m)

        total_contrib = mom_contrib + whale_contrib + spread_contrib + vol_contrib + liq_contrib
        residual = float(total_pnl) - total_contrib

        checkpoint_detail = {}
        for label, snap in cs.items():
            ck_move = _get_checkpoint_pnl(outcome, label)
            ck_direction_move = (ck_move or 0) * direction_sign
            ck_mom = _compute_momentum_contrib(adj_mom, ck_direction_move)
            ck_whale = _compute_whale_contrib({label: snap}, ck_direction_move, outcome.signal_direction or "BUY_YES")
            ck_spread = _compute_spread_contrib(entry_spread, _float(snap.get("spread_ratio")), direction_sign)
            ck_vol = _compute_volatility_contrib(entry_vol, _float(snap.get("volatility_1h")) or _float(snap.get("volatility")), entry_price)
            ck_liq = _compute_liquidity_contrib(entry_volume_5m, _float(snap.get("volume_5m")))
            ck_resid = (ck_move or 0) - (ck_mom + ck_whale + ck_spread + ck_vol + ck_liq)
            checkpoint_detail[label] = {
                "pnl": ck_move,
                "momentum_contrib": round(ck_mom, 8),
                "whale_contrib": round(ck_whale, 8),
                "spread_contrib": round(ck_spread, 8),
                "volatility_contrib": round(ck_vol, 8),
                "liquidity_contrib": round(ck_liq, 8),
                "residual": round(ck_resid, 8),
            }

        att = TradeAttribution(
            signal_outcome_id=outcome.id,
            strategy_name=outcome.strategy_name,
            entry_price=round(entry_price, 8),
            entry_momentum_1h=entry_mom,
            entry_volatility_1h=entry_vol,
            entry_spread_ratio=entry_spread,
            entry_volume_5m=entry_volume_5m,
            entry_regime=entry_regime or None,
            entry_archetype=entry_archetype if entry_archetype else "unknown",
            entry_whale_size=entry_whale,
            exit_price=_float(close_price),
            exit_momentum_1h=exit_mom,
            exit_volatility_1h=exit_vol,
            exit_spread_ratio=exit_spread,
            exit_volume_5m=exit_volume_5m,
            total_pnl=round(float(total_pnl), 8),
            momentum_contribution=round(mom_contrib, 8),
            whale_contribution=round(whale_contrib, 8),
            spread_contribution=round(spread_contrib, 8),
            volatility_contribution=round(vol_contrib, 8),
            liquidity_contribution=round(liq_contrib, 8),
            residual=round(residual, 8),
            checkpoint_attributions=checkpoint_detail or None,
            holding_time_seconds=outcome.holding_time_seconds,
        )
        self.db.add(att)
        await self.db.flush()
        return att

    async def get_attribution(self, signal_outcome_id: str) -> TradeAttribution | None:
        r = await self.db.execute(
            select(TradeAttribution).where(TradeAttribution.signal_outcome_id == signal_outcome_id)
        )
        return r.scalar_one_or_none()

    async def get_strategy_attributions(self, strategy_name: str, limit: int = 100) -> list[TradeAttribution]:
        r = await self.db.execute(
            select(TradeAttribution)
            .where(TradeAttribution.strategy_name == strategy_name)
            .order_by(TradeAttribution.created_at.desc())
            .limit(limit)
        )
        return list(r.scalars().all())


def _float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _best_checkpoint_snapshot(snapshots: dict[str, dict]) -> dict:
    for label in ("4h", "1h", "15m", "5m"):
        if label in snapshots:
            return snapshots[label]
    return {}


def _get_checkpoint_pnl(outcome: SignalOutcome, label: str) -> float | None:
    return _float(getattr(outcome, f"pnl_{label}", None))


def _compute_momentum_contrib(entry_momentum: float | None, total_move: float) -> float:
    if entry_momentum is None or total_move == 0:
        return 0.0
    if (entry_momentum > 0 and total_move > 0) or (entry_momentum < 0 and total_move < 0):
        return min(abs(total_move), abs(entry_momentum)) * (1 if total_move > 0 else -1)
    return 0.0


def _compute_whale_contrib(snapshots: dict[str, dict], total_move: float, direction: str) -> float:
    whale_impact = 0.0
    for label, snap in snapshots.items():
        size = _float(snap.get("size"))
        price = _float(snap.get("current_price"))
        side = snap.get("side", "")
        if size is not None and size >= 500 and price is not None:
            if direction == "BUY_YES" and side.lower() in ("buy", "yes"):
                whale_impact += price * 0.001
            elif direction == "BUY_NO" and side.lower() in ("sell", "no"):
                whale_impact += price * 0.001
    return min(whale_impact, abs(total_move) * 0.5) if total_move != 0 else 0.0


def _compute_spread_contrib(entry_spread: float | None, exit_spread: float | None, direction_sign: int) -> float:
    if entry_spread is None or exit_spread is None:
        return 0.0
    return (entry_spread - exit_spread) * 0.5 * direction_sign


def _compute_volatility_contrib(entry_vol: float | None, exit_vol: float | None, entry_price: float) -> float:
    if entry_vol is None or exit_vol is None:
        return 0.0
    return (exit_vol - entry_vol) * entry_price * 0.05


def _compute_liquidity_contrib(entry_vol5m: float | None, exit_vol5m: float | None) -> float:
    if entry_vol5m is None or exit_vol5m is None:
        return 0.0
    return (exit_vol5m - entry_vol5m) * 0.0001
