from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.strategies import get_strategy_names

router = APIRouter()


@router.get("/signal-distribution")
async def signal_distribution(
    epoch: str = Query(default="post_semantic_fix", description="evaluation_epoch filter"),
    days: int = Query(default=7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    from app.models import SignalOutcome
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Count by direction (infer from signal signal)
    yes_count = 0
    no_count = 0
    neutral_count = 0

    # Per-strategy distribution
    strat_dirs: dict[str, dict] = {}
    strat_conf: dict[str, list[float]] = {}

    # Per-regime distribution
    regime_dirs: dict[str, dict] = {}

    # Build outcome data
    r = await db.execute(
        select(SignalOutcome)
        .where(SignalOutcome.evaluation_epoch == epoch)
        .where(SignalOutcome.entry_timestamp >= cutoff)
    )
    outcomes = list(r.scalars().all())

    total = len(outcomes)
    if not total:
        return {"epoch": epoch, "total_signals": 0, "message": "no data for this epoch"}

    # Confidence histogram
    conf_buckets = {"0.0-0.2": 0, "0.2-0.4": 0, "0.4-0.6": 0, "0.6-0.8": 0, "0.8-1.0": 0}

    for o in outcomes:
        conf = float(o.entry_confidence) if o.entry_confidence else 0
        bucket = (
            "0.0-0.2" if conf < 0.2 else
            "0.2-0.4" if conf < 0.4 else
            "0.4-0.6" if conf < 0.6 else
            "0.6-0.8" if conf < 0.8 else
            "0.8-1.0"
        )
        conf_buckets[bucket] += 1

        # Per-strategy
        strat = o.strategy_name
        if strat not in strat_dirs:
            strat_dirs[strat] = {"BUY_YES": 0, "BUY_NO": 0, "NEUTRAL": 0}
            strat_conf[strat] = []

    # Signal direction data isn't directly on SignalOutcome, only inferred
    # For now, use entry_probability vs 0.5 as a proxy for direction
    for o in outcomes:
        prob = float(o.entry_probability) if o.entry_probability else 0.5
        strat = o.strategy_name
        # We don't have direction directly, but outcome_1h > outcome_4h can hint
        # For now, report what we have
        pass

    # Outcome types per strategy
    strat_outcomes: dict[str, dict] = {}
    for o in outcomes:
        s = o.strategy_name
        if s not in strat_outcomes:
            strat_outcomes[s] = {"WIN": 0, "LOSS": 0, "FLAT": 0, "TIMEOUT": 0}
        oc = o.outcome_close
        if oc is None:
            strat_outcomes[s]["TIMEOUT"] += 1
        else:
            strat_outcomes[s][oc] = strat_outcomes[s].get(oc, 0) + 1

    return {
        "epoch": epoch,
        "window_days": days,
        "total_signals": total,
        "confidence_histogram": conf_buckets,
        "per_strategy_outcomes": strat_outcomes,
        "per_strategy_confidences": {
            s: {
                "min": round(min(c), 4) if c else 0,
                "max": round(max(c), 4) if c else 0,
                "avg": round(sum(c) / len(c), 4) if c else 0,
            }
            for s, c in strat_conf.items()
        },
        "per_regime": regime_dirs,
    }


@router.get("/regime-performance")
async def regime_performance(
    epoch: str = Query(default="post_semantic_fix"),
    days: int = Query(default=7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    from app.models import SignalOutcome
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    r = await db.execute(
        select(SignalOutcome)
        .where(SignalOutcome.evaluation_epoch == epoch)
        .where(SignalOutcome.entry_timestamp >= cutoff)
    )
    outcomes = list(r.scalars().all())

    if not outcomes:
        return {"epoch": epoch, "total_signals": 0}

    # Group by strategy then regime
    data: dict[str, dict] = {}
    for o in outcomes:
        strat = o.strategy_name
        if strat not in data:
            data[strat] = {}
        # Regime isn't stored on SignalOutcome directly
        # Group by outcome type as a stand-in
        oc = o.outcome_close or "TIMEOUT"
        if oc not in data[strat]:
            data[strat][oc] = {"count": 0, "pnls": []}
        data[strat][oc]["count"] += 1
        if o.pnl_close is not None:
            data[strat][oc]["pnls"].append(float(o.pnl_close))

    results = {}
    for strat, outcomes_by_type in data.items():
        results[strat] = {}
        for oc_type, vals in outcomes_by_type.items():
            pnls = vals["pnls"]
            avg_pnl = sum(pnls) / len(pnls) if pnls else 0
            results[strat][oc_type] = {
                "count": vals["count"],
                "avg_pnl": round(avg_pnl, 6),
                "total_pnl": round(sum(pnls), 6),
            }

    return {"epoch": epoch, "window_days": days, "results": results}


@router.get("/replay-live-drift")
async def replay_live_drift(
    epoch: str = Query(default="post_semantic_fix"),
    days: int = Query(default=7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    from app.models import SignalOutcome, Trade
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Get signal-outcome signals (replay generated)
    r = await db.execute(
        select(SignalOutcome)
        .where(SignalOutcome.evaluation_epoch == epoch)
        .where(SignalOutcome.entry_timestamp >= cutoff)
    )
    outcomes = list(r.scalars().all())

    # Get live trades
    r2 = await db.execute(
        select(Trade)
        .where(Trade.created_at >= cutoff)
    )
    trades = list(r2.scalars().all())

    return {
        "epoch": epoch,
        "window_days": days,
        "replay_signals": len(outcomes),
        "live_trades": len(trades),
        "live_trades_detail": [
            {
                "id": str(t.id),
                "side": t.side,
                "outcome": t.outcome,
                "filled_price": float(t.filled_price) if t.filled_price else None,
                "pnl": float(t.pnl) if t.pnl else None,
                "status": t.status,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in trades[:20]
        ],
        "replay_outcomes_sample": [
            {
                "strategy": o.strategy_name,
                "entry_probability": float(o.entry_probability) if o.entry_probability else None,
                "outcome_close": o.outcome_close,
                "pnl_close": float(o.pnl_close) if o.pnl_close else None,
            }
            for o in outcomes[:50]
        ],
    }


@router.get("/strategy-summary")
async def strategy_summary(
    epoch: str = Query(default="post_semantic_fix"),
    days: int = Query(default=7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    from app.models import SignalOutcome

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    names = get_strategy_names()
    rankings = []

    for name in names:
        try:
            # Filter outcomes by epoch
            r = await db.execute(
                select(SignalOutcome)
                .where(SignalOutcome.strategy_name == name)
                .where(SignalOutcome.evaluation_epoch == epoch)
                .where(SignalOutcome.entry_timestamp >= cutoff)
                .limit(1000)
            )
            outcomes = list(r.scalars().all())
            if not outcomes:
                rankings.append({"strategy": name, "total_signals": 0, "epoch": epoch})
                continue

            total = len(outcomes)
            wins = sum(1 for o in outcomes if o.outcome_close == "WIN")
            losses = sum(1 for o in outcomes if o.outcome_close == "LOSS")
            flats = sum(1 for o in outcomes if o.outcome_close == "FLAT")
            timed_out = sum(1 for o in outcomes if o.outcome_close is None)

            win_rate = wins / total if total > 0 else 0
            pnls = [float(o.pnl_close) for o in outcomes if o.pnl_close is not None]
            avg_pnl = sum(pnls) / len(pnls) if pnls else 0

            win_pnls = [float(o.pnl_close) for o in outcomes if o.outcome_close == "WIN" and o.pnl_close is not None]
            loss_pnls = [float(o.pnl_close) for o in outcomes if o.outcome_close == "LOSS" and o.pnl_close is not None]
            avg_win = sum(win_pnls) / len(win_pnls) if win_pnls else 0
            avg_loss = abs(sum(loss_pnls) / len(loss_pnls)) if loss_pnls else 0
            expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss) if avg_loss > 0 else 0

            sharpe = 0
            if len(pnls) > 1:
                mean_pnl = sum(pnls) / len(pnls)
                variance = sum((p - mean_pnl) ** 2 for p in pnls) / len(pnls)
                std = variance ** 0.5
                sharpe = (mean_pnl / std) * (252 ** 0.5) if std > 0 else 0

            drawdowns = []
            peak = float("-inf")
            cumulative = 0
            for pnl in pnls:
                cumulative += pnl
                if cumulative > peak:
                    peak = cumulative
                drawdown = peak - cumulative
                drawdowns.append(drawdown)
            max_dd = max(drawdowns) if drawdowns else 0

            rankings.append({
                "strategy": name,
                "epoch": epoch,
                "total_signals": total,
                "wins": wins,
                "losses": losses,
                "flats": flats,
                "timed_out": timed_out,
                "win_rate": round(win_rate, 4),
                "avg_pnl": round(avg_pnl, 6),
                "avg_win": round(avg_win, 6),
                "avg_loss": round(avg_loss, 6),
                "expectancy": round(expectancy, 6),
                "sharpe_ratio": round(sharpe, 4),
                "max_drawdown": round(max_dd, 6),
                "total_pnl": round(sum(pnls), 6),
            })
        except Exception as e:
            rankings.append({"strategy": name, "error": str(e)})

    rankings.sort(key=lambda r: r.get("sharpe_ratio", 0) or 0, reverse=True)
    return {"rankings": rankings}


@router.get("/slippage-summary")
async def slippage_summary(
    days: int = Query(default=7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    from app.models import Trade
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    r = await db.execute(
        select(Trade)
        .where(Trade.status == "closed")
        .where(Trade.exit_timestamp >= cutoff)
    )
    trades = list(r.scalars().all())

    if not trades:
        return {"total_trades": 0, "avg_slippage": 0, "total_slippage_usd": 0}

    total_slippage = sum(float(t.slippage or 0) for t in trades)
    avg_slippage = total_slippage / len(trades)

    # Estimate USD impact if possible, or just report the ratio
    return {
        "total_trades": len(trades),
        "avg_slippage": round(avg_slippage, 6),
        "total_slippage_sum": round(total_slippage, 6),
        "period_days": days
    }


@router.get("/attribution")
async def alpha_vs_beta_attribution(
    hours: int = Query(default=168, ge=1, le=8760),
    db: AsyncSession = Depends(get_db),
):
    from app.services.benchmark_service import BenchmarkService
    service = BenchmarkService(db)
    return await service.compute_alpha_vs_beta(hours=hours)

