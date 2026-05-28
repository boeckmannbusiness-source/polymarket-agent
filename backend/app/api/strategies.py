from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.strategies import get_strategy, list_strategies, get_strategy_names
from app.services.strategy_service import StrategyService
from app.services.signal_evaluation_service import SignalEvaluationService
from app.services.signal_service import SignalService
from app.replay.engine import ReplayEngine, ReplayMode

router = APIRouter()


@router.get("/")
async def list_all_strategies():
    return list_strategies()


@router.get("/names")
async def list_strategy_names():
    return {"strategies": get_strategy_names()}


@router.get("/rankings")
async def get_strategy_rankings(db: AsyncSession = Depends(get_db)):
    names = get_strategy_names()
    eval_service = SignalEvaluationService(db)
    rankings = []
    for name in names:
        try:
            summary = await eval_service.get_strategy_summary(name)
            rankings.append(summary)
        except Exception:
            rankings.append({"strategy": name, "total_signals": 0})

    rankings.sort(key=lambda r: r.get("sharpe_ratio", 0) or 0, reverse=True)
    return rankings


@router.get("/{strategy_name}")
async def get_strategy_detail(strategy_name: str, db: AsyncSession = Depends(get_db)):
    try:
        strategy = get_strategy(strategy_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    service = StrategyService(db)
    config_row = await service.get_config(strategy_name)
    perf = await service.get_performance(strategy_name)

    return {
        "metadata": strategy.get_metadata(),
        "config": config_row.config if config_row else strategy.config.model_dump(),
        "performance": [
            {
                "total_signals": p.total_signals,
                "executed_signals": p.executed_signals,
                "win_rate": float(p.win_rate) if p.win_rate else None,
                "avg_confidence": float(p.avg_confidence) if p.avg_confidence else None,
                "total_pnl": float(p.total_pnl) if p.total_pnl else None,
            }
            for p in perf
        ],
    }


@router.get("/{strategy_name}/performance")
async def get_strategy_performance(strategy_name: str, db: AsyncSession = Depends(get_db)):
    try:
        get_strategy(strategy_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    eval_service = SignalEvaluationService(db)
    summary = await eval_service.get_strategy_summary(strategy_name)
    return summary


@router.get("/{strategy_name}/signals")
async def get_strategy_signals(
    strategy_name: str,
    limit: int = Query(default=100, le=1000),
    db: AsyncSession = Depends(get_db),
):
    try:
        get_strategy(strategy_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    signal_service = SignalService(db)
    signals = await signal_service.list_signals(
        signal_type=strategy_name,
        limit=limit,
    )
    return [
        {
            "id": str(s.id),
            "direction": s.direction,
            "confidence": float(s.confidence),
            "reasoning": s.reasoning,
            "signal_type": s.signal_type,
            "generated_at": s.generated_at.isoformat() if s.generated_at else None,
            "is_active": s.is_active,
        }
        for s in signals
    ]


@router.get("/{strategy_name}/outcomes")
async def get_strategy_outcomes(
    strategy_name: str,
    limit: int = Query(default=100, le=1000),
    db: AsyncSession = Depends(get_db),
):
    try:
        get_strategy(strategy_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    eval_service = SignalEvaluationService(db)
    outcomes = await eval_service.get_outcomes(strategy_name, limit=limit)
    return [
        {
            "id": str(o.id),
            "entry_timestamp": o.entry_timestamp.isoformat() if o.entry_timestamp else None,
            "entry_probability": float(o.entry_probability) if o.entry_probability else None,
            "outcome_5m": o.outcome_5m,
            "outcome_15m": o.outcome_15m,
            "outcome_1h": o.outcome_1h,
            "outcome_4h": o.outcome_4h,
            "outcome_close": o.outcome_close,
            "max_favorable_excursion": float(o.max_favorable_excursion) if o.max_favorable_excursion else None,
            "max_adverse_excursion": float(o.max_adverse_excursion) if o.max_adverse_excursion else None,
            "reversal_count": o.reversal_count,
            "holding_time_seconds": o.holding_time_seconds,
        }
        for o in outcomes
    ]


@router.post("/{strategy_name}/replay")
async def run_strategy_replay(
    strategy_name: str,
    start_days: int = Query(default=7, description="Days of history to replay"),
    db: AsyncSession = Depends(get_db),
):
    try:
        get_strategy(strategy_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=start_days)

    engine = ReplayEngine(db)
    result = await engine.run(
        strategy_name=strategy_name,
        start_time=start,
        end_time=end,
        mode=ReplayMode.SIGNAL_ONLY,
    )

    eval_service = SignalEvaluationService(db)
    for signal in result.signals:
        await eval_service.evaluate_replayed_signal(signal)
    await db.commit()

    return {
        "strategy": strategy_name,
        "mode": result.mode.value,
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "total_events_processed": result.total_events_processed,
        "signals_generated": result.signals_generated,
        "signals": [
            {
                "signal": s.signal.signal,
                "confidence": s.signal.confidence,
                "reason": s.signal.reason[:100] if s.signal.reason else "",
                "entry_price": s.entry_price,
                "regime": s.regime,
                "outcome_5m": s.outcome_5m,
                "outcome_15m": s.outcome_15m,
                "outcome_1h": s.outcome_1h,
                "outcome_4h": s.outcome_4h,
                "outcome_close": s.outcome_close,
                "max_favorable_excursion": s.max_favorable_excursion,
                "max_adverse_excursion": s.max_adverse_excursion,
            }
            for s in result.signals[:50]
        ],
    }


@router.get("/{strategy_name}/regimes")
async def get_strategy_regime_performance(strategy_name: str, db: AsyncSession = Depends(get_db)):
    try:
        get_strategy(strategy_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    eval_service = SignalEvaluationService(db)
    outcomes = await eval_service.get_outcomes(strategy_name, limit=1000)

    regimes: dict[str, dict] = {}
    for o in outcomes:
        label = "no_outcome"
        if o.outcome_close == "WIN":
            label = "win"
        elif o.outcome_close == "LOSS":
            label = "loss"
        elif o.outcome_close == "FLAT":
            label = "flat"
        else:
            label = "pending"

        if label not in regimes:
            regimes[label] = {"count": 0, "total_pnl": 0.0}
        regimes[label]["count"] += 1
        if o.pnl_close is not None:
            regimes[label]["total_pnl"] += float(o.pnl_close)

    return regimes
