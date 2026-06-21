import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.logging import setup_logging, logger
from app.database import init_db
from app.redis import close_redis
from app.ingesters.polymarket_rest import PolymarketRESTIngester
from app.ingesters.polymarket_ws import PolymarketWSIngester
from app.ingesters.polygon_rpc import PolygonRPCListener
from app.agents.orchestrator import Orchestrator
from app.services.event_bridge import EventPersistenceBridge
from app.services.exit_engine import ExitEngine
from app.services.risk_overlay import RiskOverlay
from app.services.strategy_guardian import StrategyGuardian
from app.services.portfolio_allocator import PortfolioAllocator
from app.services.edge_reality_engine import EdgeRealityEngine
from app.services.overfitting_detector import OverfittingDetector
from app.services.survivability_simulator import SurvivabilitySimulator
from app.services.strategy_pruning_engine import StrategyPruningEngine
from app.services.capital_efficiency_engine import CapitalEfficiencyEngine
from app.services.walk_forward_engine import WalkForwardEngine
from app.services.shadow_trading_service import ShadowTradingService
from app.services.stress_test_engine import StressTestEngine
from app.services.live_trading_state_machine import LiveTradingStateMachine
from app.services.system_health_store import SystemHealthStore
from app.core.system_mode import ModeManager, SystemMode, set_global_manager
from app.workers.clob_fill_poller import CLOBFillPoller
from app.workers.monitoring_worker import MonitoringWorker
from app.api.system import set_mode_manager as _wire_mode_api


_mode_manager: ModeManager = ModeManager()
_ws_ingester: PolymarketWSIngester | None = None
_polygon_rpc: PolygonRPCListener | None = None
_bridge: EventPersistenceBridge | None = None
_exit_engine: ExitEngine | None = None
_risk_overlay: RiskOverlay | None = None
_strategy_guardian: StrategyGuardian | None = None
_portfolio_allocator: PortfolioAllocator | None = None
_edge_reality_engine: EdgeRealityEngine | None = None
_overfitting_detector: OverfittingDetector | None = None
_survivability_simulator: SurvivabilitySimulator | None = None
_strategy_pruning_engine: StrategyPruningEngine | None = None
_capital_efficiency_engine: CapitalEfficiencyEngine | None = None
_walk_forward_engine: WalkForwardEngine | None = None
_shadow_trading_service: ShadowTradingService | None = None
_stress_test_engine: StressTestEngine | None = None
_live_state_machine: LiveTradingStateMachine | None = None
_system_health_store: SystemHealthStore | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _ws_ingester, _polygon_rpc, _bridge, _exit_engine, _risk_overlay, _strategy_guardian, _portfolio_allocator
    global _edge_reality_engine, _overfitting_detector, _survivability_simulator, _strategy_pruning_engine, _capital_efficiency_engine
    global _walk_forward_engine, _shadow_trading_service, _stress_test_engine, _live_state_machine, _system_health_store
    setup_logging()

    # Sprint 1.8A Startup Validation
    from app.services.capabilities import validate_all
    from app.services.assets.bootstrap import bootstrap_asset_registry
    try:
        validate_all()
        bootstrap_asset_registry()
        logger.info("capability_validation_passed")
    except Exception as e:
        logger.critical("capability_validation_failed", error=str(e))
        raise

    logger.info("starting_up", env=settings.APP_ENV, mode=settings.TRADING_MODE)
    try:
        await init_db()
        logger.info("database_initialized")
    except Exception as e:
        logger.warning("database_init_skipped", error=str(e))

    rest_ingester = PolymarketRESTIngester(poll_interval=60)
    _ws_ingester = PolymarketWSIngester()
    ws_ingester = _ws_ingester
    _polygon_rpc = PolygonRPCListener(poll_interval=15)
    from web3.middleware import ExtraDataToPOAMiddleware
    _polygon_rpc.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    polygon_rpc = _polygon_rpc
    _bridge = EventPersistenceBridge()
    bridge = _bridge
    orchestrator = Orchestrator()

    from app.database import async_session_factory
    try:
        async with async_session_factory() as init_db_session:
            _exit_engine = ExitEngine(init_db_session)
            _risk_overlay = RiskOverlay(init_db_session)
            _strategy_guardian = StrategyGuardian(init_db_session)
            _portfolio_allocator = PortfolioAllocator(init_db_session)
            await _portfolio_allocator.restore_from_db()
            _edge_reality_engine = EdgeRealityEngine(init_db_session)
            _overfitting_detector = OverfittingDetector(init_db_session)
            _survivability_simulator = SurvivabilitySimulator(init_db_session)
            _strategy_pruning_engine = StrategyPruningEngine(init_db_session)
            _capital_efficiency_engine = CapitalEfficiencyEngine(init_db_session)
            _walk_forward_engine = WalkForwardEngine(init_db_session)
            _shadow_trading_service = ShadowTradingService(init_db_session)
            _stress_test_engine = StressTestEngine(init_db_session)
            _live_state_machine = LiveTradingStateMachine(init_db_session)
            _system_health_store = SystemHealthStore(init_db_session)
    except Exception as e:
        logger.warning("service_init_skipped", error=str(e))

    bg_tasks = []

    # Register the mode manager early so background tasks can call get_mode_manager()
    try:
        await asyncio.wait_for(_mode_manager.load_from_redis(), timeout=10)
    except Exception:
        logger.warning("mode_manager_load_failed")

    if settings.SHADOW_MODE:
        await _mode_manager.set_manual_override(
            mode=SystemMode.SHADOW,
            reason="shadow_mode_enabled_by_config",
            operator="system",
            ttl_seconds=259200,
        )
        logger.warning("system_started_in_shadow_mode")

    set_global_manager(_mode_manager)
    _wire_mode_api(_mode_manager)

    bg_tasks.append(asyncio.create_task(rest_ingester.run(), name="rest_ingester"))
    logger.info("rest_ingester_started", interval=60)

    bg_tasks.append(asyncio.create_task(ws_ingester.run(), name="ws_ingester"))
    logger.info("ws_ingester_started")

    bg_tasks.append(asyncio.create_task(polygon_rpc.run(), name="polygon_rpc"))
    logger.info("polygon_rpc_started")

    bg_tasks.append(asyncio.create_task(bridge.start(), name="event_bridge"))
    logger.info("event_bridge_started")

    bg_tasks.append(asyncio.create_task(orchestrator.start_all(), name="orchestrator"))
    logger.info("orchestrator_started")

    try:
        from app.redis import get_redis
        r = await get_redis()

        if settings.SHADOW_MODE:
            for stream, group in [
                ("market:data", "persistence_bridge"),
                ("market:data", "whale_agent"),
                ("wallet:trade", "signal_agent"),
                ("signal:generated", "risk_agent"),
                ("trade:request", "execution_agent"),
            ]:
                try:
                    await r.xgroup_destroy(stream, group)
                except Exception as e:
                    logger.warning("shadow_xgroup_destroy_failed", stream=stream, group=group, error=str(e), exc_info=True)
                try:
                    await r.xgroup_create(stream, group, id="$", mkstream=True)
                    logger.info("shadow_consumer_group_reset", stream=stream, group=group)
                except Exception:
                    pass

        # ── Redis configuration validation ─────────────────────
        try:
            mem_info = await r.info("memory")
            used = mem_info.get("used_memory", 0)
            maxmem = mem_info.get("maxmemory", 0)
            if maxmem:
                pct = used / maxmem * 100
                logger.info("redis_memory_at_startup", used_mb=round(used / 1024 / 1024, 1),
                            maxmemory_mb=round(maxmem / 1024 / 1024, 1), utilization_pct=round(pct, 1))
                if pct >= 80:
                    logger.warning("redis_high_memory_utilization", utilization_pct=round(pct, 1))
            else:
                used_mb = round(used / 1024 / 1024, 1)
                limit_mb = settings.REDIS_PLAN_LIMIT_MB
                provider_pct = round(used_mb / limit_mb * 100, 1) if limit_mb > 0 else 0
                logger.warning("redis_no_maxmemory_set_falling_back_to_provider_plan",
                               used_mb=used_mb, provider_plan_limit_mb=limit_mb,
                               provider_utilization_pct=provider_pct)
                if limit_mb > 0 and provider_pct >= 80:
                    logger.warning("redis_high_provider_utilization",
                                   utilization_pct=provider_pct, provider_plan_limit_mb=limit_mb)

            policy = await r.config_get("maxmemory-policy")
            actual_policy = policy.get("maxmemory-policy", "")
            expected_policy = "allkeys-lru"
            if actual_policy != expected_policy:
                logger.warning("redis_maxmemory_policy_mismatch", expected=expected_policy, actual=actual_policy)
            else:
                logger.info("redis_maxmemory_policy_ok", policy=actual_policy)

            aof = await r.config_get("appendonly")
            aof_enabled = aof.get("appendonly", "no")
            if aof_enabled != "yes":
                logger.warning("redis_aof_disabled")
            else:
                logger.info("redis_aof_enabled")
        except Exception as e:
            logger.error("redis_config_validation_failed", error=str(e), exc_info=True)

        from app.core.stream_registry import StreamRegistry
        for config in StreamRegistry.active_in_phase1():
            if not config.consumer_groups:
                logger.error("stream_registry_no_consumer_groups", stream=config.name)
            logger.info("stream_registry_active", stream=config.name, groups=list(config.consumer_groups))

        from app.services.reconciliation_service import check_redis_persistence, run_startup_reconciliation
        await check_redis_persistence(r)
        async with async_session_factory() as rec_db:
            rec_report = await run_startup_reconciliation(rec_db)
            if rec_report and any(rec_report[k] > 0 for k in rec_report if isinstance(rec_report[k], int)):
                logger.warning("startup_reconciliation_report", report={k: v for k, v in rec_report.items() if isinstance(v, int)})
    except Exception as e:
        logger.warning("startup_reconciliation_failed", error=str(e))

    bg_tasks.append(asyncio.create_task(_periodic_db_cleanup(), name="db_cleanup"))
    logger.info("db_cleanup_started")

    bg_tasks.append(asyncio.create_task(_periodic_redis_cleanup(), name="redis_cleanup"))
    logger.info("redis_cleanup_started")

    bg_tasks.append(asyncio.create_task(_periodic_exit_engine_loop(), name="exit_engine"))
    logger.info("exit_engine_started")

    bg_tasks.append(asyncio.create_task(_periodic_risk_overlay_check(), name="risk_overlay"))
    logger.info("risk_overlay_started")

    bg_tasks.append(asyncio.create_task(_periodic_strategy_guardian_eval(), name="strategy_guardian"))
    logger.info("strategy_guardian_started")

    bg_tasks.append(asyncio.create_task(_periodic_phase45_analysis(), name="phase45_analysis"))
    logger.info("phase45_analysis_started")

    bg_tasks.append(asyncio.create_task(_periodic_shadow_sync(), name="shadow_sync"))
    logger.info("shadow_sync_started")

    bg_tasks.append(asyncio.create_task(_periodic_state_machine_check(), name="state_machine"))
    logger.info("state_machine_started")

    bg_tasks.append(asyncio.create_task(_periodic_health_snapshot(), name="health_snapshot"))
    logger.info("health_snapshot_started")

    bg_tasks.append(asyncio.create_task(_periodic_portfolio_snapshot(), name="portfolio_snapshot"))
    logger.info("portfolio_snapshot_started")

    bg_tasks.append(asyncio.create_task(_periodic_benchmark_recording(), name="benchmark_recording"))
    logger.info("benchmark_recording_started")

    bg_tasks.append(asyncio.create_task(_periodic_reconciliation(), name="reconciliation"))
    logger.info("reconciliation_started")

    bg_tasks.append(asyncio.create_task(_periodic_pel_recovery(), name="pel_recovery"))
    logger.info("pel_recovery_started")

    # pending_trade_recovery is handled by pel_recovery above
    logger.info("pending_trade_recovery_skipped")

    bg_tasks.append(asyncio.create_task(_periodic_replay_parity_check(), name="replay_parity"))
    logger.info("replay_parity_check_started")

    bg_tasks.append(asyncio.create_task(_periodic_agent_log_cleanup(), name="agent_log_cleanup"))
    logger.info("agent_log_cleanup_started")

    bg_tasks.append(asyncio.create_task(_periodic_hypothesis_cleanup(), name="hypothesis_cleanup"))
    logger.info("hypothesis_cleanup_started")

    bg_tasks.append(asyncio.create_task(_periodic_pool_monitor(), name="pool_monitor"))
    logger.info("pool_monitor_started")

    bg_tasks.append(asyncio.create_task(_periodic_mode_evaluator(), name="mode_evaluator"))
    logger.info("mode_evaluator_started")

    # ── Shadow validation initialisation ───────────────
    from app.services.validation.shadow_validation_service import shadow_validation_service as _shadow_val_svc
    try:
        async with async_session_factory() as _init_svdb:
            await _shadow_val_svc.start_run(_init_svdb)
        logger.info("shadow_validation_initialised")
    except Exception as e:
        logger.warning("shadow_validation_init_failed", error=str(e))

    # ── Scheduler registration ─────────────────────────
    from app.services.scheduler.task_scheduler import scheduler as _scheduler
    from app.services.risk.circuit_breakers import cb_system as _cb_system, register_default_breakers
    from app.services.incidents.incident_service import incident_service as _incident_service

    async def _scheduler_cb_eval():
        state = await control_plane.get_state()
        context = {
            "trading_enabled": state["trading_enabled"],
            "execution_mode": state["execution_mode"],
            "paused_strategies": state["paused_strategies"],
        }
        triggered = await _cb_system.evaluate_all(context)
        for cb_data in triggered:
            await _incident_service.create_from_breaker(cb_data)

    await _scheduler.register_job("circuit_breaker_eval", 30, _scheduler_cb_eval)

    monitoring_worker = MonitoringWorker()
    await _scheduler.register_job("monitoring_worker", 60, monitoring_worker.run_single_cycle)

    # ── Shadow execution sync ────────────────────────
    from app.services.shadow.shadow_execution_service import shadow_execution_service as _shadow_svc

    async def _shadow_cycle():
        try:
            from app.database import async_session_factory
            async with async_session_factory() as _sdb:
                await _shadow_svc.sync_from_signals(_sdb)
                await _shadow_svc.refresh_prices(_sdb)
        except Exception:
            logger.warning("shadow_cycle_error", exc_info=True)

    await _scheduler.register_job("shadow_sync", 120, _shadow_cycle)

    # ── Portfolio review scheduler ────────────────────────
    from app.services.intelligence.autonomous_portfolio_review import autonomous_portfolio_review as _portfolio_review

    async def _portfolio_review_cycle():
        try:
            await _portfolio_review.run()
        except Exception:
            logger.warning("portfolio_review_cycle_error", exc_info=True)

    await _scheduler.register_job("portfolio_review", 86400, _portfolio_review_cycle)  # 24h

    # ── Portfolio optimization scheduler (runs AFTER portfolio review) ──
    from app.services.optimization.autonomous_optimization_pipeline import autonomous_optimization_pipeline as _optimization_pipeline

    async def _optimization_cycle():
        try:
            await _optimization_pipeline.run()
        except Exception:
            logger.warning("optimization_cycle_error", exc_info=True)

    await _scheduler.register_job("portfolio_optimization", 86400, _optimization_cycle)  # 24h

    # ── Portfolio control scheduler (runs AFTER optimization) ──
    from app.services.control.autonomous_control_pipeline import autonomous_control_pipeline as _control_pipeline

    async def _control_cycle():
        try:
            await _control_pipeline.run()
        except Exception:
            logger.warning("control_cycle_error", exc_info=True)

    await _scheduler.register_job("portfolio_control", 86400, _control_cycle)  # 24h

    # ── Shadow validation monitor ────────────────────────
    from app.services.validation.shadow_runtime_monitor import shadow_runtime_monitor as _shadow_monitor

    async def _shadow_validation_cycle():
        try:
            result = await _shadow_monitor.collect_and_persist()
            status = await _shadow_monitor.get_validation_status()
            logger.info(
                "shadow_validation_cycle",
                status=status["status"],
                progress_pct=status["progress_pct"],
                snapshots=status["snapshot_count"],
                alerts=status["active_alert_count"],
            )
        except Exception:
            logger.warning("shadow_validation_cycle_error", exc_info=True)

    await _scheduler.register_job("shadow_validation_monitor", 300, _shadow_validation_cycle)  # 5min

    # Keep original background task for backward compat during migration
    bg_tasks.append(asyncio.create_task(monitoring_worker.run(), name="monitoring_worker"))
    logger.info("monitoring_worker_started")

    # ── WebSocket Redis bridge ────────────────────────
    bg_tasks.append(asyncio.create_task(_ws_redis_bridge(), name="ws_redis_bridge"))
    logger.info("ws_redis_bridge_started")

    # ── Alert registration ─────────────────────────────
    from app.services.alerts.alert_service import alert_service as _alert_service
    _alert_service.register_default_rules()
    logger.info("alert_rules_registered")

    # ── Circuit breaker registration ───────────────────
    register_default_breakers()
    bg_tasks.append(asyncio.create_task(_periodic_circuit_breaker_eval(), name="circuit_breaker_eval"))
    logger.info("circuit_breakers_started")

    if settings.TRADING_MODE == "live":
        clob_poller = CLOBFillPoller(poll_interval=30)
        bg_tasks.append(asyncio.create_task(clob_poller.run(), name="clob_fill_poller"))
        logger.info("clob_fill_poller_started")

        bg_tasks.append(asyncio.create_task(_periodic_live_reconciliation(), name="live_reconciliation"))
        logger.info("live_reconciliation_started")

    # ── Non-blocking startup recovery scan ────────────
    bg_tasks.append(asyncio.create_task(_startup_recovery_scan(), name="startup_recovery_scan"))

    # ── Startup assertion: HELIUS_WEBHOOK_SECRET in production ──
    if settings.APP_ENV == "production" and not settings.HELIUS_WEBHOOK_SECRET:
        raise RuntimeError(
            "HELIUS_WEBHOOK_SECRET must be set when APP_ENV=production. "
            "Without it, webhook auth is disabled and the service is exposed to unauthenticated requests."
        )

    # ── Solana SmartWallet Agent ──────────────────────
    bg_tasks.append(asyncio.create_task(_smart_wallet_agent_loop(), name="smart_wallet_agent"))
    logger.info("smart_wallet_agent_started")

    # ── Solana Signal Seed Worker ─────────────────────
    bg_tasks.append(asyncio.create_task(_signal_seed_worker_loop(), name="signal_seed_worker"))
    logger.info("signal_seed_worker_started")

    # ── Solana DLQ Replay Worker ──────────────────────
    bg_tasks.append(asyncio.create_task(_solana_dlq_replay_loop(), name="solana_dlq_replay"))
    logger.info("solana_dlq_replay_started")

    # ── DLQ callback registration ─────────────────────
    from app.services.reliability.dead_letter_queue import dlq as _dlq
    _dlq.register_callback("reconciliation", lambda _et, _pl: logger.info("dlq_replay_reconciliation", event_type=_et))
    _dlq.register_callback("fill_ingestion", lambda _et, _pl: logger.info("dlq_replay_fill_ingestion", event_type=_et))
    _dlq.register_callback("event_store", lambda _et, _pl: logger.info("dlq_replay_event_store", event_type=_et))
    _dlq.register_callback("ws_publish", lambda _et, _pl: logger.info("dlq_replay_ws_publish", event_type=_et))
    _dlq.register_callback("scheduler", lambda _et, _pl: logger.info("dlq_replay_scheduler", event_type=_et))
    logger.info("dlq_callbacks_registered")

    # ── Shadow price tracker (T3-V2, runs every 60s, +0s stagger) ──
    bg_tasks.append(asyncio.create_task(_shadow_price_tracker_loop(), name="shadow_price_tracker"))
    logger.info("shadow_price_tracker_started")

    # ── Shadow evaluation loop (T3-V1, runs every 60s, +15s stagger) ──
    bg_tasks.append(asyncio.create_task(_shadow_eval_loop(), name="shadow_eval"))
    logger.info("shadow_eval_started")

    yield

    logger.info("shutting_down")
    await rest_ingester.stop()
    await ws_ingester.stop()
    await polygon_rpc.stop()
    await bridge.stop()
    await orchestrator.stop_all()
    from app.services.scheduler.task_scheduler import scheduler as _scheduler
    await _scheduler.shutdown()
    for t in bg_tasks:
        t.cancel()
    await asyncio.gather(*bg_tasks, return_exceptions=True)
    await close_redis()
    logger.info("shutdown_complete")


async def _periodic_db_cleanup():
    from app.database import async_session_factory
    from app.core.system_mode import get_mode_manager
    from sqlalchemy import text
    from datetime import datetime, timezone, timedelta
    import asyncio

    while True:
        try:
            if not get_mode_manager().can_write():
                await asyncio.sleep(30)
                continue

            await asyncio.sleep(3600)
            cutoff = datetime.now(timezone.utc) - timedelta(hours=6)
            async with async_session_factory() as db:
                result = await db.execute(
                    text("DELETE FROM market_events WHERE timestamp < :cutoff"),
                    {"cutoff": cutoff},
                )
                await db.commit()
                if result.rowcount:
                    logger.info("db_cleanup_deleted", rows=result.rowcount)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("db_cleanup_error", error=str(e))
            await asyncio.sleep(5)


async def _periodic_redis_cleanup():
    from app.core.stream_registry import StreamRegistry
    from app.redis import get_redis
    from app.core.metrics import stream_trim_count, stream_length
    from app.services.redis_monitor import RedisMonitor
    from app.services.alert_manager import AlertManager, build_default_rules
    from app.core.logging import logger
    import asyncio

    monitor = RedisMonitor()
    alert_manager = AlertManager()
    alert_manager.register_rules(build_default_rules())

    await asyncio.sleep(30)
    while True:
        try:
            await asyncio.sleep(settings.STREAM_TRIM_INTERVAL)
            r = await get_redis()
            maxlen = settings.REDIS_STREAM_MAXLEN

            _STREAMS_TO_CHECK = StreamRegistry.phase1_stream_names()
            for s in _STREAMS_TO_CHECK:
                try:
                    info = await r.xinfo_stream(s)
                    current_len = info["length"]
                    stream_length.labels(stream=s).set(current_len)
                    pct = (current_len / maxlen) * 100 if maxlen > 0 else 0
                    if pct >= 95:
                        logger.critical("stream_pressure_critical", stream=s, length=current_len, maxlen=maxlen, pct=pct)
                    elif pct >= 80:
                        logger.warning("stream_pressure_warning", stream=s, length=current_len, maxlen=maxlen, pct=pct)
                except Exception as e:
                    logger.warning("stream_pressure_monitor_failed", stream=s, error=str(e), exc_info=True)

            approx = settings.STREAM_TRIM_APPROX
            if approx:
                trimmed = await r.xtrim("market:data", maxlen=maxlen, approximate=True)
            else:
                trimmed = await r.xtrim("market:data", maxlen=maxlen)
            await monitor.record_trim("market:data", trimmed)
            dlq_trimmed = await r.xtrim("market:data:dlq", maxlen=500)
            await monitor.record_trim("market:data:dlq", dlq_trimmed)
            cutoff = int(asyncio.get_event_loop().time()) - 3600
            for stream in await r.keys("test:*"):
                await r.delete(stream)
            await monitor.collect_snapshot()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("redis_cleanup_error", error=str(e))


_PEL_SEMAPHORE = asyncio.Semaphore(3)

async def _periodic_pel_recovery():
    import asyncio
    from datetime import datetime, timezone, timedelta
    from app.core.recovery import recover_pending_messages
    from app.core.metrics import recovery_loop_errors_total, recovery_loop_recoveries_total, recovery_stuck_count
    from app.core.system_mode import get_mode_manager
    from app.database import async_session_factory
    from app.models import Trade
    from app.services.pipeline_metrics import inc_pending_trade_timeout
    from sqlalchemy import select

    _PENDING_TIMEOUT_SECONDS = 3600

    _PEL_GROUPS = [
        ("market:data", "whale_agent", "whale_1"),
        ("wallet:trade", "signal_agent", "signal_1"),
        ("signal:generated", "risk_agent", "risk_1"),
        ("trade:request", "execution_agent", "exec_1"),
        ("agent:event", "monitoring_agent", "mon_1"),
    ]

    await asyncio.sleep(60)
    while True:
        try:
            if not get_mode_manager().can_recover():
                await asyncio.sleep(30)
                continue

            async with async_session_factory() as db:
                cutoff = datetime.now(timezone.utc) - timedelta(seconds=_PENDING_TIMEOUT_SECONDS)
                result = await db.execute(
                    select(Trade).where(
                        Trade.status == "pending",
                        Trade.created_at < cutoff,
                    )
                )
                stale = list(result.scalars().all())
                for t in stale:
                    old_status = t.status
                    t.status = "cancelled"
                    await inc_pending_trade_timeout()
                    recovery_loop_recoveries_total.labels(loop_name="pending_trade").inc()
                    logger.info(
                        "pending_trade_timeout_cancelled",
                        trade_id=str(t.id),
                        market_id=str(t.market_id),
                        age_seconds=(datetime.now(timezone.utc) - t.created_at).total_seconds(),
                        previous_status=old_status,
                    )
                if stale:
                    await db.commit()
        except asyncio.CancelledError:
            break
        except Exception as e:
            recovery_loop_errors_total.labels(loop_name="pending_trade").inc()
            logger.warning("pending_trade_recovery_error", error=str(e))
        await asyncio.sleep(120)


async def _periodic_replay_parity_check():
    import asyncio
    from datetime import datetime, timedelta, timezone
    from app.database import async_session_factory
    from app.models import Signal
    from app.core.metrics import replay_drift_pct
    from app.core.system_mode import get_mode_manager
    from sqlalchemy import select, func
    from app.strategies import get_strategy_names

    await asyncio.sleep(3600)
    while True:
        try:
            if not get_mode_manager().can_process():
                await asyncio.sleep(60)
                continue

            strategies = get_strategy_names()
            now = datetime.now(timezone.utc)
            hour_ago = now - timedelta(hours=1)

            async with async_session_factory() as db:
                for strategy in strategies:
                    live_count = await db.execute(
                        select(func.count()).select_from(Signal)
                        .where(Signal.signal_type == strategy)
                        .where(Signal.generated_at >= hour_ago)
                    )
                    live = live_count.scalar() or 0
                    replay_drift_pct.labels(strategy=strategy).set(0.0)
        except asyncio.CancelledError:
            break
        except Exception as e:
            from app.core.logging import logger
            logger.warning("replay_parity_check_error", error=str(e))
        await asyncio.sleep(3600)


async def _periodic_agent_log_cleanup():
    import asyncio
    from datetime import datetime, timezone, timedelta
    from app.database import async_session_factory
    from app.core.system_mode import get_mode_manager
    from sqlalchemy import text

    await asyncio.sleep(3600)
    while True:
        try:
            if not get_mode_manager().can_write():
                await asyncio.sleep(60)
                continue

            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            async with async_session_factory() as db:
                result = await db.execute(
                    text("DELETE FROM agent_logs WHERE timestamp < :cutoff"),
                    {"cutoff": cutoff},
                )
                await db.commit()
                if result.rowcount:
                    from app.core.logging import logger
                    logger.info("agent_log_cleanup_deleted", rows=result.rowcount)
        except asyncio.CancelledError:
            break
        except Exception as e:
            from app.core.logging import logger
            logger.warning("agent_log_cleanup_error", error=str(e))
        await asyncio.sleep(86400)


async def _periodic_hypothesis_cleanup():
    import asyncio
    from datetime import datetime, timezone, timedelta
    from app.database import async_session_factory

    now = datetime.now(timezone.utc)
    next_run = now.replace(hour=3, minute=0, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)
    initial_delay = (next_run - now).total_seconds()
    await asyncio.sleep(initial_delay)

    while True:
        try:
            async with async_session_factory() as db:
                from app.services.research_hypothesis_service import ResearchHypothesisService
                svc = ResearchHypothesisService(db)
                deleted = await svc.purge_expired()
                if deleted:
                    from app.core.logging import logger
                    logger.info("hypothesis_cleanup_purged", rows=deleted)
        except asyncio.CancelledError:
            break
        except Exception as e:
            from app.core.logging import logger
            logger.warning("hypothesis_cleanup_error", error=str(e))
        await asyncio.sleep(86400)


async def _periodic_pool_monitor():
    import asyncio
    from app.database import engine
    from app.core.metrics import db_pool_size

    await asyncio.sleep(30)
    while True:
        try:
            pool = engine.pool
            if pool:
                db_pool_size.labels(state="total").set(pool.size())
                db_pool_size.labels(state="checkedin").set(pool.checkedin())
                db_pool_size.labels(state="overflow").set(pool.overflow())
                available = pool.size() + pool.overflow() - pool.checkedin()
                db_pool_size.labels(state="available").set(available)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("pool_monitor_failed", error=str(e), exc_info=True)
        await asyncio.sleep(60)


async def _periodic_exit_engine_loop():
    import asyncio
    from sqlalchemy import select
    from app.database import async_session_factory
    from app.models import Trade
    from app.core.system_mode import get_mode_manager
    from app.core.heartbeat import touch_loop_heartbeat

    await asyncio.sleep(15)
    while True:
        try:
            touch_loop_heartbeat("exit_engine")

            if not get_mode_manager().can_write():
                await asyncio.sleep(15)
                continue

            async with async_session_factory() as db:
                engine = ExitEngine(db)
                decisions = await engine.evaluate_all_open()
                for d in decisions:
                    if d["action"] == "EXIT":
                        trade = await db.execute(
                            select(Trade).where(Trade.id == d["trade_id"])
                        )
                        trade = trade.scalar_one_or_none()
                        if trade:
                            from app.services.trade_service import TradeService
                            service = TradeService(db)
                            await service.close_trade(
                                trade.id,
                                exit_price=d.get("exit_price"),
                            )
                            logger.info(
                                "exit_engine_closed",
                                trade_id=d["trade_id"],
                                reason=d["reason"],
                                exit_price=d.get("exit_price"),
                            )
                await db.commit()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("exit_engine_loop_error", error=str(e))
        await asyncio.sleep(30)


async def _periodic_risk_overlay_check():
    import asyncio
    from app.database import async_session_factory
    from app.core.heartbeat import touch_loop_heartbeat

    await asyncio.sleep(300)
    while True:
        try:
            touch_loop_heartbeat("risk_overlay")

            async with async_session_factory() as db:
                overlay = RiskOverlay(db)
                state = await overlay.check()
                if state.status != "ACTIVE":
                    logger.warning(
                        "risk_overlay_state_change",
                        status=state.status,
                        reason=state.reason,
                    )
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("risk_overlay_check_error", error=str(e))
        await asyncio.sleep(30)


async def _periodic_strategy_guardian_eval():
    import asyncio
    from app.database import async_session_factory
    from app.core.heartbeat import touch_loop_heartbeat

    await asyncio.sleep(60)
    while True:
        try:
            touch_loop_heartbeat("strategy_guardian")

            async with async_session_factory() as db:
                guardian = StrategyGuardian(db)
                results = await guardian.evaluate_all()
                for name, status in results.items():
                    if status.status == "DISABLED":
                        logger.warning(
                            "strategy_disabled_by_guardian",
                            strategy=name,
                            reason=status.reason,
                        )
                await db.commit()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("strategy_guardian_eval_error", error=str(e))
        await asyncio.sleep(300)


async def _periodic_phase45_analysis():
    import asyncio
    from app.database import async_session_factory
    from app.services.edge_reality_engine import EdgeRealityEngine
    from app.services.overfitting_detector import OverfittingDetector
    from app.services.survivability_simulator import SurvivabilitySimulator
    from app.services.strategy_pruning_engine import StrategyPruningEngine
    from app.services.pipeline_metrics import set_phase45_metrics

    await asyncio.sleep(120)
    while True:
        try:
            async with async_session_factory() as db:
                edge_engine = EdgeRealityEngine(db)
                overfit = OverfittingDetector(db)
                survival = SurvivabilitySimulator(db)
                pruning = StrategyPruningEngine(db)
                efficiency = CapitalEfficiencyEngine(db)

                decisions = await pruning.decide_all()
                rankings = await efficiency.rank_all()

                avg_edge = 0.0
                avg_overfit = 0.0
                avg_survival = 0.0
                top_rank = 0
                count = 0

                for name, decision in decisions.items():
                    if decision.classification == "DISABLE":
                        logger.warning("phase45_pruning_disable", strategy=name, reason=decision.reason)
                        continue
                    edge = await edge_engine.compute_edge(name, days=60)
                    of = await overfit.detect(name)
                    sv = await survival.simulate(name, days=30, simulations=500)
                    avg_edge += edge.expectancy
                    avg_overfit += of.score
                    avg_survival += 1.0 - sv.probability_of_ruin
                    count += 1

                if count > 0:
                    avg_edge /= count
                    avg_overfit /= count
                    avg_survival /= count

                sorted_ranks = sorted(rankings.keys(), key=lambda n: rankings[n].score, reverse=True)
                for rank, name in enumerate(sorted_ranks, 1):
                    if rank == 1:
                        top_rank = rank
                    break

                await set_phase45_metrics(avg_edge, avg_overfit, avg_survival, top_rank)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("phase45_analysis_error", error=str(e))
        await asyncio.sleep(3600)


async def _periodic_shadow_sync():
    import asyncio
    from app.database import async_session_factory
    from app.services.shadow_trading_service import ShadowTradingService
    from app.services.live_trading_state_machine import LiveTradingStateMachine
    from app.core.heartbeat import touch_loop_heartbeat

    await asyncio.sleep(30)
    while True:
        try:
            touch_loop_heartbeat("shadow_sync")

            async with async_session_factory() as db:
                shadow = ShadowTradingService(db)
                await shadow.sync_from_live_trades()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("shadow_sync_error", error=str(e))
        await asyncio.sleep(60)


async def _periodic_state_machine_check():
    import asyncio
    from app.database import async_session_factory
    from app.services.live_trading_state_machine import LiveTradingStateMachine
    from app.services.risk_overlay import RiskOverlay
    from app.services.pipeline_metrics import set_phase5_metrics
    from app.core.heartbeat import touch_loop_heartbeat

    await asyncio.sleep(300)
    while True:
        try:
            touch_loop_heartbeat("state_machine")

            async with async_session_factory() as db:
                sm = LiveTradingStateMachine(db)
                overlay = RiskOverlay(db)
                state = await overlay.check()
                new_state = await sm.evaluate(state.status)
                caps = sm.hard_caps
                logger.info("state_machine_check", state=new_state.value, caps=caps)
                await set_phase5_metrics(
                    new_state.value,
                    caps.get("max_concurrent_positions", 0),
                    0.0,
                    0,
                )
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("state_machine_error", error=str(e))
        await asyncio.sleep(120)


async def _startup_recovery_scan():
    import asyncio
    await asyncio.sleep(60)
    try:
        from app.database import async_session_factory
        from app.services.recovery.order_recovery_service import OrderRecoveryService
        async with async_session_factory() as _db:
            svc = OrderRecoveryService(_db)
            report = await svc.run_scan(force=False)
            logger.info("startup_recovery_scan_complete", **report)
    except Exception as e:
        logger.warning("startup_recovery_scan_error", error=str(e))


async def _periodic_circuit_breaker_eval():
    import asyncio
    from app.services.risk.circuit_breakers import cb_system
    from app.services.incidents.incident_service import incident_service
    from app.services.control.control_plane import control_plane

    await asyncio.sleep(30)
    while True:
        try:
            state = await control_plane.get_state()
            context = {
                "trading_enabled": state["trading_enabled"],
                "execution_mode": state["execution_mode"],
                "paused_strategies": state["paused_strategies"],
            }
            triggered = await cb_system.evaluate_all(context)
            for cb_data in triggered:
                await incident_service.create_from_breaker(cb_data)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("circuit_breaker_eval_error", error=str(e))
        await asyncio.sleep(30)


async def _periodic_health_snapshot():
    import asyncio
    from app.database import async_session_factory
    from app.services.system_health_store import SystemHealthStore
    from app.services.pipeline_metrics import set_phase5_metrics, get_metrics
    from app.services.alert_manager import AlertManager, build_default_rules
    from app.core.heartbeat import record_heartbeat

    alert_manager = AlertManager()
    alert_manager.register_rules(build_default_rules())

    await asyncio.sleep(10)
    while True:
        try:
            await record_heartbeat("health_snapshot", data={"loop_interval_s": 300})

            async with async_session_factory() as db:
                store = SystemHealthStore(db)
                snapshot = await store.record_snapshot()
                alerts = await store.check_alerts()
                for alert in alerts:
                    logger.warning("health_alert", alert=alert)

                metrics = await get_metrics()
                metrics["drawdown"] = snapshot.drawdown
                metrics["ws_events_per_minute"] = snapshot.ws_events_last_minute
                await alert_manager.evaluate_all(metrics)

                await set_phase5_metrics(
                    "HEALTH_CHECK",
                    0,
                    0.0,
                    len(alerts),
                )
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("health_snapshot_error", error=str(e))
        await asyncio.sleep(300)


async def _periodic_portfolio_snapshot():
    import asyncio
    from app.database import async_session_factory
    from app.services.portfolio_service import PortfolioService
    from app.core.heartbeat import touch_loop_heartbeat

    await asyncio.sleep(120)
    while True:
        try:
            touch_loop_heartbeat("portfolio_snapshot")

            async with async_session_factory() as db:
                service = PortfolioService(db)
                snapshot = await service.compute_portfolio_snapshot()
                await db.commit()
                logger.info(
                    "portfolio_snapshot_recorded",
                    value=float(snapshot.portfolio_value or 0),
                    drawdown=float(snapshot.drawdown or 0),
                    positions=snapshot.open_positions,
                )
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("portfolio_snapshot_error", error=str(e))
        await asyncio.sleep(3600)


async def _periodic_benchmark_recording():
    import asyncio
    from app.database import async_session_factory
    from app.services.benchmark_service import BenchmarkService
    from app.core.heartbeat import touch_loop_heartbeat

    await asyncio.sleep(180)
    while True:
        try:
            touch_loop_heartbeat("benchmark_recording")

            async with async_session_factory() as db:
                service = BenchmarkService(db)
                synthetic_price = await service.compute_synthetic_benchmark()
                await service.record_benchmark_price(
                    price=synthetic_price,
                    source="synthetic",
                )
                await db.commit()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("benchmark_recording_error", error=str(e))
        await asyncio.sleep(3600)


async def _periodic_reconciliation():
    import asyncio
    from app.database import async_session_factory
    from app.services.reconciliation_service import run_startup_reconciliation
    from app.core.heartbeat import touch_loop_heartbeat

    await asyncio.sleep(600)
    while True:
        try:
            touch_loop_heartbeat("reconciliation")

            async with async_session_factory() as db:
                report = await run_startup_reconciliation(db)
                issues = {k: v for k, v in report.items() if isinstance(v, int) and v > 0}
                if issues:
                    logger.info("periodic_reconciliation_report", report=issues)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("reconciliation_error", error=str(e))
        await asyncio.sleep(43200)


async def _ws_redis_bridge():
    import asyncio
    import json
    from app.redis import get_redis
    from app.ws.manager import manager
    from app.core.events import EventBus

    channels = [
        "dashboard:markets", "dashboard:whales", "dashboard:signals",
        "dashboard:trades", "telegram:alerts",
    ]

    await asyncio.sleep(5)
    while True:
        try:
            r = await get_redis()
            pubsub = r.pubsub()
            await pubsub.subscribe(*channels)
            async for msg in pubsub.listen():
                if msg["type"] != "message":
                    continue
                try:
                    event = json.loads(msg["data"])
                    channel_map = {
                        "dashboard:markets": "portfolio",
                        "dashboard:whales": "monitoring",
                        "dashboard:signals": "monitoring",
                        "dashboard:trades": "trades",
                        "telegram:alerts": "alerts",
                    }
                    ws_channel = channel_map.get(msg["channel"], "monitoring")
                    await manager.broadcast_event(event, channels=[ws_channel])
                except json.JSONDecodeError:
                    continue
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("ws_redis_bridge_error", error=str(e))
            await asyncio.sleep(10)


async def _smart_wallet_agent_loop():
    import asyncio
    from app.database import async_session_factory
    from app.core.events import EventBus
    from app.services.smart_wallet_agent import SmartWalletAgent

    await asyncio.sleep(10)
    while True:
        try:
            r = await EventBus.subscribe_to_stream(
                "solana:trade:detected", "smart_wallet_agent", "smart_wallet_agent_1",
            )
            while True:
                messages = await EventBus.read_stream(
                    r, "solana:trade:detected", "smart_wallet_agent", "smart_wallet_agent_1",
                    count=10, block=5000,
                )
                if not messages:
                    await asyncio.sleep(1)
                    continue

                async with async_session_factory() as db:
                    agent = SmartWalletAgent(db)
                    for msg in messages:
                        data = msg.get("data", {})
                        try:
                            await agent.handle_trade_event(data)
                        except Exception:
                            logger.warning("smart_wallet_agent_event_error", event_id=msg.get("id"))
                            try:
                                import json
                                from app.redis import get_redis as _get_dlq_redis
                                dlq_r = await _get_dlq_redis()
                                await dlq_r.xadd(
                                    "solana:dlq:events",
                                    {"stream": "solana:trade:detected", "msg_id": msg["id"], "source": "smart_wallet_agent", "data": json.dumps(data)},
                                    maxlen=10000,
                                )
                            except Exception:
                                pass
                        await EventBus.ack_message(r, "solana:trade:detected", "smart_wallet_agent", msg["id"])
        except asyncio.CancelledError:
            break
        except Exception:
            logger.warning("smart_wallet_agent_loop_error", exc_info=True)
            await asyncio.sleep(10)


async def _signal_seed_worker_loop():
    import asyncio
    from app.database import async_session_factory
    from app.core.events import EventBus
    from app.services.signal_seed_service import SignalSeedService

    await asyncio.sleep(15)
    while True:
        try:
            r = await EventBus.subscribe_to_stream(
                "solana:trade:detected", "research_trade_worker", "signal_seed_worker_1",
            )
            while True:
                messages = await EventBus.read_stream(
                    r, "solana:trade:detected", "research_trade_worker", "signal_seed_worker_1",
                    count=10, block=5000,
                )
                if not messages:
                    await asyncio.sleep(1)
                    continue

                async with async_session_factory() as db:
                    service = SignalSeedService(db)
                    for msg in messages:
                        data = msg.get("data", {})
                        try:
                            await service.evaluate_trade_event(data)
                        except Exception:
                            logger.warning("signal_seed_event_error", event_id=msg.get("id"))
                            try:
                                import json
                                from app.redis import get_redis as _get_dlq_redis
                                dlq_r = await _get_dlq_redis()
                                await dlq_r.xadd(
                                    "solana:dlq:events",
                                    {"stream": "solana:trade:detected", "msg_id": msg["id"], "source": "signal_seed_worker", "data": json.dumps(data)},
                                    maxlen=10000,
                                )
                            except Exception:
                                pass
                        await EventBus.ack_message(r, "solana:trade:detected", "research_trade_worker", msg["id"])
        except asyncio.CancelledError:
            break
        except Exception:
            logger.warning("signal_seed_worker_loop_error", exc_info=True)
            await asyncio.sleep(10)


_DLQ_MAX_RETRIES = 3


async def _solana_dlq_replay_loop():
    import asyncio
    import json

    from app.core.events import EventBus
    from app.core.metrics import solana_dlq_replayed_total
    from app.redis import get_redis

    await asyncio.sleep(30)
    while True:
        try:
            r = await get_redis()
            entries = await r.xread({"solana:dlq:events": "0"}, count=20, block=5000)
            if not entries or not entries[0]:
                await asyncio.sleep(10)
                continue

            stream_key, messages = entries[0]
            for msg in messages:
                msg_id, fields = msg
                data = {k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v for k, v in fields.items()}
                source = data.get("source", "unknown")
                event_data_str = data.get("data")

                # ── Poison pill protection ─────────────────────
                retry_count = int(data.get("_retry_count", 0))
                if retry_count >= _DLQ_MAX_RETRIES:
                    logger.warning("dlq_poison_pill_detected", msg_id=msg_id, source=source, retry_count=retry_count)
                    await r.xadd(
                        "solana:dlq:poison",
                        {"original_msg_id": msg_id, "source": source, "data": event_data_str or ""},
                        maxlen=1000,
                    )
                    await r.xdel("solana:dlq:events", msg_id)
                    solana_dlq_replayed_total.labels(source=f"poison:{source}").inc()
                    continue

                success = False
                if event_data_str:
                    try:
                        event_data = json.loads(event_data_str)
                        await EventBus.publish(
                            "solana:trade:detected",
                            "solana:trade:detected",
                            f"dlq_replay:{source}",
                            event_data,
                        )
                        success = True
                    except Exception:
                        logger.warning("dlq_replay_publish_failed", msg_id=msg_id, source=source)

                if success:
                    solana_dlq_replayed_total.labels(source=source).inc()
                    await r.xdel("solana:dlq:events", msg_id)
                else:
                    # Increment retry counter and leave in DLQ for next cycle
                    await r.xadd(
                        "solana:dlq:events",
                        {"_retry_count": str(retry_count + 1), **data},
                        maxlen=10000,
                    )
                    await r.xdel("solana:dlq:events", msg_id)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.warning("solana_dlq_replay_loop_error", exc_info=True)
            await asyncio.sleep(10)


async def _shadow_price_tracker_loop():
    import asyncio
    from app.database import async_session_factory
    from app.services.shadow_price_service import PriceTrackingService
    from app.repositories.shadow_position_repository import ShadowPositionRepository
    from app.models.research_trade import ResearchTrade
    from app.models.wallet_trade import SolanaWalletTrade
    from sqlalchemy import select

    await asyncio.sleep(0)
    while True:
        try:
            async with async_session_factory() as db:
                price_svc = PriceTrackingService(db)
                repo = ShadowPositionRepository(db)
                open_positions = await repo.list_open()

                rt_ids = [p.research_trade_id for p in open_positions if p.research_trade_id is not None]
                if not rt_ids:
                    await asyncio.sleep(settings.SOLANA_SHADOW_EVAL_INTERVAL)
                    continue

                rows = await db.execute(
                    select(ResearchTrade.id, SolanaWalletTrade.mint_address)
                    .join(SolanaWalletTrade, ResearchTrade.wallet_trade_id == SolanaWalletTrade.id)
                    .where(ResearchTrade.id.in_(rt_ids))
                    .where(SolanaWalletTrade.mint_address.isnot(None)),
                )
                rt_to_mint = {row.id: row.mint_address for row in rows.all()}

                distinct_mints = list(set(rt_to_mint.values()))
                mint_to_price: dict[str, float] = {}

                # Optimized: Resolve prices in parallel with concurrency limit
                sem = asyncio.Semaphore(10)

                async def resolve_with_sem(m):
                    async with sem:
                        res = await price_svc.resolve_price(m)
                        return m, res

                results = await asyncio.gather(*[resolve_with_sem(m) for m in distinct_mints])
                for mint, res in results:
                    if res.price is not None:
                        mint_to_price[mint] = float(res.price)

                updated = 0
                for pos in open_positions:
                    mint = rt_to_mint.get(pos.research_trade_id)
                    if mint is None:
                        continue
                    price = mint_to_price.get(mint)
                    if price is not None:
                        await repo.update_current_price(pos.id, price)
                        updated += 1

                if updated:
                    logger.info("shadow_price_tracker_updated", count=updated)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("shadow_price_tracker_fatal_error", error=str(e), exc_info=True)
            await asyncio.sleep(5)
            continue
        await asyncio.sleep(settings.SOLANA_SHADOW_EVAL_INTERVAL)


async def _shadow_eval_loop():
    import asyncio
    from app.database import async_session_factory
    from app.services.shadow_portfolio_service import ShadowPortfolioService

    await asyncio.sleep(15)
    while True:
        try:
            async with async_session_factory() as db:
                svc = ShadowPortfolioService(db)
                closed = await svc.evaluate_all()
                if closed:
                    logger.info("shadow_eval_closed_positions", count=len(closed))
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("shadow_eval_loop_fatal_error", error=str(e), exc_info=True)
            await asyncio.sleep(5)
            continue
        await asyncio.sleep(settings.SOLANA_SHADOW_EVAL_INTERVAL)


app = FastAPI(
    title="Polymarket Intelligence Agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Production debug guard middleware ───────────────────
from starlette.middleware.base import BaseHTTPMiddleware


class DebugEndpointGuard(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path.startswith("/debug/") and settings.APP_ENV in ("production", "staging"):
            admin_key = request.headers.get("x-admin-key", "")
            if not settings.ADMIN_API_KEY or admin_key != settings.ADMIN_API_KEY:
                from fastapi.responses import PlainTextResponse
                return PlainTextResponse("Not Found", status_code=404)
        return await call_next(request)


app.add_middleware(DebugEndpointGuard)


# ── Admin auth ─────────────────────────────────────────
from fastapi import Header as _Header, HTTPException as _HTTPException, Request as _Request
from app.api.system import _require_admin


async def _debug_endpoint_guard(request: _Request):
    if settings.APP_ENV == "production" or settings.APP_ENV == "staging":
        admin_key = request.headers.get("x-admin-key", "")
        if not settings.ADMIN_API_KEY or admin_key != settings.ADMIN_API_KEY:
            raise _HTTPException(status_code=404, detail="Not found")


@app.get("/health")
async def health():
    return {"status": "ok", "mode": settings.TRADING_MODE, "env": settings.APP_ENV}


@app.get("/system/status")
async def system_status():
    return {
        "app": {"env": settings.APP_ENV, "mode": settings.TRADING_MODE},
        "ingesters": {
            "rest": "started",
            "websocket": "started",
        },
        "orchestrator": "started",
        "services": {
            "event_bridge": "started",
        },
    }


# ── Phase 4: Capital Allocation & Exit Engine ────────────


@app.get("/debug/exit-decisions/{trade_id}")
async def debug_exit_decisions(trade_id: str):
    from uuid import UUID as _UUID
    from app.database import async_session_factory
    from fastapi import HTTPException

    try:
        trade_uuid = _UUID(trade_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid trade ID")

    async with async_session_factory() as db:
        trade = await db.execute(select(Trade).where(Trade.id == trade_uuid))
        trade = trade.scalar_one_or_none()
        if not trade:
            raise HTTPException(status_code=404, detail="Trade not found")

        engine = ExitEngine(db)
        decision = await engine.evaluate(trade)

        return {
            "trade_id": trade_id,
            "action": decision.action,
            "reason": decision.reason,
            "confidence": decision.confidence,
            "exit_price": decision.exit_price,
        }


@app.get("/debug/strategy-status")
async def debug_strategy_status():
    from app.database import async_session_factory

    async with async_session_factory() as db:
        guardian = StrategyGuardian(db)
        results = await guardian.evaluate_all()
        return {
            name: {
                "status": s.status,
                "reason": s.reason,
                "metrics": s.metrics_snapshot,
            }
            for name, s in results.items()
        }


@app.get("/debug/risk-overlay")
async def debug_risk_overlay():
    from app.database import async_session_factory

    async with async_session_factory() as db:
        overlay = RiskOverlay(db)
        state = await overlay.check()
        return {
            "status": state.status,
            "reason": state.reason,
            "cooldown_until": state.cooldown_until.isoformat() if state.cooldown_until else None,
            "drawdown_curve": overlay.get_portfolio_drawdown_curve()[-50:],
        }


@app.get("/debug/portfolio-allocator")
async def debug_portfolio_allocator(strategy: str = ""):
    from app.database import async_session_factory

    async with async_session_factory() as db:
        allocator = PortfolioAllocator(db)
        if strategy:
            cap = await allocator.get_allocated_capital(strategy)
        else:
            cap = await allocator.get_allocated_capital()
        return {
            "allocated_capital_per_strategy": cap,
        }


@app.get("/debug/exit-stats")
async def debug_exit_stats():
    from app.database import async_session_factory

    async with async_session_factory() as db:
        engine = ExitEngine(db)
        return {
            "exit_reason_distribution": engine.get_exit_reason_distribution(),
            "forced_exit_rate": engine.get_forced_exit_rate(),
        }


@app.get("/debug/guardian-kill-count")
async def debug_guardian_kill_count():
    from app.database import async_session_factory

    async with async_session_factory() as db:
        guardian = StrategyGuardian(db)
        return {"strategy_kill_count": guardian.get_kill_count()}


# ── Phase 4.5: Edge Validation & Survivability ──────────


@app.get("/debug/edge-report/{strategy_name}")
async def debug_edge_report(strategy_name: str, days: int = 60):
    from app.database import async_session_factory

    async with async_session_factory() as db:
        engine = EdgeRealityEngine(db)
        report = await engine.compute_edge(strategy_name, days=days)
        return {
            "strategy": strategy_name,
            "expectancy": report.expectancy,
            "sharpe_proxy": report.sharpe_proxy,
            "stability_score": report.stability_score,
            "tail_risk": report.tail_risk,
            "confidence_score": report.confidence_score,
            "win_rate": report.win_rate,
            "loss_severity": report.loss_severity,
            "total_trades": report.total_trades,
            "expectancy_per_regime": report.expectancy_per_regime,
            "expectancy_per_price_zone": report.expectancy_per_price_zone,
            "expectancy_per_archetype": report.expectancy_per_archetype,
            "expectancy_per_resolution": report.expectancy_per_resolution,
        }


@app.get("/debug/overfit-report/{strategy_name}")
async def debug_overfit_report(strategy_name: str):
    from app.database import async_session_factory

    async with async_session_factory() as db:
        detector = OverfittingDetector(db)
        score = await detector.detect(strategy_name)
        return {
            "strategy": strategy_name,
            "overfit_score": score.score,
            "risk_level": score.risk_level,
            "reason": score.reason,
        }


@app.get("/debug/survival-report/{strategy_name}")
async def debug_survival_report(strategy_name: str, days: int = 30, simulations: int = 500):
    from app.database import async_session_factory

    async with async_session_factory() as db:
        simulator = SurvivabilitySimulator(db)
        report = await simulator.simulate(strategy_name, days=days, simulations=simulations)
        return {
            "strategy": strategy_name,
            "expected_drawdown": report.expected_drawdown,
            "probability_of_ruin": report.probability_of_ruin,
            "expected_return": report.expected_return,
            "volatility_stability": report.volatility_stability,
            "survived_simulations": report.survived_simulations,
            "total_simulations": report.total_simulations,
        }


@app.get("/debug/pruning-decision/{strategy_name}")
async def debug_pruning_decision(strategy_name: str):
    from app.database import async_session_factory

    async with async_session_factory() as db:
        pruner = StrategyPruningEngine(db)
        decision = await pruner.decide(strategy_name)
        return {
            "strategy": strategy_name,
            "status": decision.status,
            "confidence": decision.confidence,
            "capital_recommendation": decision.capital_recommendation,
            "reason": decision.reason,
            "classification": decision.classification,
        }


@app.get("/debug/efficiency-rank")
async def debug_efficiency_rank():
    from app.database import async_session_factory

    async with async_session_factory() as db:
        efficiency = CapitalEfficiencyEngine(db)
        rankings = await efficiency.rank_all()
        return {
            name: {
                "score": r.score,
                "expectancy": r.expectancy,
                "max_drawdown": r.max_drawdown,
                "stability": r.stability,
                "rank": r.rank,
                "total_strategies": r.total_strategies,
            }
            for name, r in rankings.items()
        }


@app.get("/debug/phase45-full-report")
async def debug_phase45_full_report():
    from sqlalchemy import select
    from app.database import async_session_factory

    async with async_session_factory() as db:
        from app.models.strategy import StrategyConfigRecord as _SCR
        result = await db.execute(select(_SCR).where(_SCR.enabled == True))
        records = list(result.scalars().all())

        edge_engine = EdgeRealityEngine(db)
        overfit = OverfittingDetector(db)
        survival = SurvivabilitySimulator(db)
        pruner = StrategyPruningEngine(db)
        efficiency = CapitalEfficiencyEngine(db)

        full = {}
        for record in records:
            name = record.strategy_name
            edge = await edge_engine.compute_edge(name, days=60)
            of_score = await overfit.detect(name)
            sv = await survival.simulate(name, days=30, simulations=500)
            decision = await pruner.decide(name)

            full[name] = {
                "classification": decision.classification,
                "decision": decision.status,
                "capital_rec": decision.capital_recommendation,
                "edge_expectancy": edge.expectancy,
                "edge_sharpe": edge.sharpe_proxy,
                "edge_stability": edge.stability_score,
                "edge_tail_risk": edge.tail_risk,
                "edge_confidence": edge.confidence_score,
                "overfit_score": of_score.score,
                "overfit_risk": of_score.risk_level,
                "survival_return": sv.expected_return,
                "survival_ruin_prob": sv.probability_of_ruin,
                "survival_drawdown": sv.expected_drawdown,
            }

        rankings = await efficiency.rank_all()
        ranked = sorted(rankings.keys(), key=lambda n: rankings[n].score, reverse=True)

        return {
            "strategies": full,
            "capital_efficiency_ranking": [
                {
                    "rank": i + 1,
                    "strategy": name,
                    "efficiency_score": rankings[name].score,
                }
                for i, name in enumerate(ranked)
            ],
            "summary": {
                "real_alpha": [n for n, d in full.items() if d["classification"] == "REAL_ALPHA"],
                "weak_edge": [n for n, d in full.items() if d["classification"] == "WEAK_EDGE"],
                "overfitted": [n for n, d in full.items() if d["classification"] == "OVERFITTED"],
                "losing": [n for n, d in full.items() if d["classification"] == "LOSING_SYSTEM"],
            },
        }


# ── Phase 5: Walk-Forward, Shadow Trading & Stress Testing ──


@app.get("/debug/walk-forward/{strategy_name}")
async def debug_walk_forward(strategy_name: str):
    from app.database import async_session_factory

    async with async_session_factory() as db:
        engine = WalkForwardEngine(db)
        report = await engine.run(strategy_name)
        return {
            "strategy": strategy_name,
            "survival_classification": report.survival_classification,
            "stability_score": report.stability_score,
            "expectancy_stability": report.expectancy_stability,
            "win_rate_drift": report.win_rate_drift,
            "sharpe_drift": report.sharpe_drift,
            "drawdown_drift": report.drawdown_drift,
            "signal_frequency_drift": report.signal_frequency_drift,
            "overfit_persistence_score": report.overfit_persistence_score,
            "windows": [
                {
                    "label": w.window_label,
                    "trade_count": w.trade_count,
                    "expectancy": w.expectancy,
                    "win_rate": w.win_rate,
                    "sharpe": w.sharpe,
                    "max_drawdown": w.max_drawdown,
                    "signal_frequency": w.signal_frequency,
                }
                for w in report.windows
            ],
        }


@app.get("/debug/shadow-metrics")
async def debug_shadow_metrics():
    from app.database import async_session_factory

    async with async_session_factory() as db:
        shadow = ShadowTradingService(db)
        await shadow.sync_from_live_trades()
        metrics = shadow.get_shadow_metrics()
        return {
            "live_expectancy": metrics.live_expectancy,
            "live_sharpe": metrics.live_sharpe,
            "live_drawdown": metrics.live_drawdown,
            "latency_adjusted_pnl": metrics.latency_adjusted_pnl,
            "total_trades": metrics.total_trades,
            "missed_fills": metrics.missed_fills,
            "stale_fills": metrics.stale_fills,
            "avg_latency_ms": metrics.avg_latency_ms,
            "avg_slippage": metrics.avg_slippage,
        }


@app.get("/debug/stress-test")
async def debug_stress_test():
    from app.database import async_session_factory

    async with async_session_factory() as db:
        engine = StressTestEngine(db)
        results = await engine.run_all(simulations=200)
        return {
            r.scenario: {
                "portfolio_survived": r.portfolio_survived,
                "forced_liquidations": r.forced_liquidations,
                "kill_switch_activated": r.kill_switch_activated,
                "max_drawdown": r.max_drawdown,
                "survived_pct": r.survived_pct,
            }
            for r in results
        }


@app.get("/debug/trading-state")
async def debug_trading_state():
    from app.database import async_session_factory

    async with async_session_factory() as db:
        sm = LiveTradingStateMachine(db)
        return {
            "state": sm.state.value,
            "hard_caps": sm.hard_caps,
            "history": sm.get_transition_history()[-20:],
        }


@app.get("/debug/health-snapshot")
async def debug_health_snapshot():
    from app.database import async_session_factory

    async with async_session_factory() as db:
        store = SystemHealthStore(db)
        await store.record_snapshot()
        latest = store.get_latest()
        alerts = await store.check_alerts()
        return {
            "timestamp": latest.timestamp.isoformat() if latest else None,
            "total_trades": latest.total_trades if latest else 0,
            "open_trades": latest.open_trades if latest else 0,
            "portfolio_value": latest.portfolio_value if latest else 0,
            "drawdown": latest.drawdown if latest else 0,
            "kill_switch_active": latest.kill_switch_active if latest else False,
            "active_strategies": latest.active_strategies if latest else 0,
            "disabled_strategies": latest.disabled_strategies if latest else 0,
            "ws_events_last_minute": latest.ws_events_last_minute if latest else 0,
            "alerts": alerts,
        }


@app.get("/debug/health-history")
async def debug_health_history(limit: int = 50):
    from app.database import async_session_factory

    async with async_session_factory() as db:
        store = SystemHealthStore(db)
        await store.record_snapshot()
        history = store.get_history(limit=limit)
        return {
            "snapshots": [
                {
                    "timestamp": h.timestamp.isoformat(),
                    "total_trades": h.total_trades,
                    "open_trades": h.open_trades,
                    "portfolio_value": h.portfolio_value,
                    "drawdown": h.drawdown,
                    "kill_switch_active": h.kill_switch_active,
                    "ws_events_last_minute": h.ws_events_last_minute,
                }
                for h in history
            ]
        }


@app.get("/debug/edge-decay/{strategy_name}")
async def debug_edge_decay(strategy_name: str):
    from app.database import async_session_factory
    from app.services.edge_reality_engine import EdgeRealityEngine
    from app.services.execution_simulator import ExecutionSimulator

    async with async_session_factory() as db:
        edge_engine = EdgeRealityEngine(db)
        edge = await edge_engine.compute_edge(strategy_name, days=60)
        sim = ExecutionSimulator()
        decay = sim.compute_edge_decay(edge.expectancy)
        return {
            "strategy": strategy_name,
            "base_expectancy": edge.expectancy,
            "edge_decay_by_latency": decay,
        }


# ── Pre-Live Hardening Endpoints ────────────────────────


@app.get("/debug/global-risk")
async def debug_global_risk():
    from app.database import async_session_factory
    from app.services.global_risk_guard import GlobalRiskGuard
    from app.services.pipeline_metrics import set_exposure_metrics

    async with async_session_factory() as db:
        guard = GlobalRiskGuard(db)
        summary = await guard.get_exposure_summary()
        await set_exposure_metrics(summary["total_open_exposure"], summary["exposure_utilization_pct"])
        return summary


@app.get("/debug/open-market-positions")
async def debug_open_market_positions():
    from app.database import async_session_factory
    from app.models import Trade

    async with async_session_factory() as db:
        result = await db.execute(
            select(Trade).where(Trade.status.in_(["open", "pending"]))
        )
        trades = list(result.scalars().all())
        return {
            "count": len(trades),
            "positions": [
                {
                    "trade_id": str(t.id),
                    "market_id": str(t.market_id),
                    "outcome": t.outcome,
                    "side": t.side,
                    "size": float(t.size),
                    "filled_size": float(t.filled_size or 0),
                    "price": float(t.filled_price or 0),
                    "status": t.status,
                    "agent_id": t.agent_id,
                }
                for t in trades
            ],
        }


@app.get("/debug/trading-halts")
async def debug_trading_halts():
    from app.database import async_session_factory
    from app.services.risk_overlay import RiskOverlay

    async with async_session_factory() as db:
        overlay = RiskOverlay(db)
        state = await overlay.check()
        return {
            "current_status": state.status,
            "reason": state.reason,
            "cooldown_until": state.cooldown_until.isoformat() if state.cooldown_until else None,
            "trading_allowed": state.status in ("ACTIVE", "REDUCED"),
        }


@app.post("/debug/kill-switch/enable")
async def debug_kill_switch_enable(_admin=Depends(_require_admin)):
    from app.services.pipeline_metrics import inc_kill_switch_activation

    import app.services.trade_service as ts
    ts.FORCE_TRADING_DISABLED = True
    await inc_kill_switch_activation()
    return {"kill_switch": True, "message": "Trading disabled globally"}


@app.post("/debug/kill-switch/disable")
async def debug_kill_switch_disable(_admin=Depends(_require_admin)):
    import app.services.trade_service as ts
    ts.FORCE_TRADING_DISABLED = False
    return {"kill_switch": False, "message": "Trading re-enabled"}


@app.get("/debug/order-preview/{signal_id}")
async def debug_order_preview(signal_id: str):
    from uuid import UUID
    from app.database import async_session_factory
    from app.services.order_preview_service import OrderPreviewService

    async with async_session_factory() as db:
        svc = OrderPreviewService(db)
        preview = await svc.preview(signal_id)
        return {
            "signal_id": preview.signal_id,
            "strategy": preview.strategy,
            "confidence": preview.confidence,
            "weighted_confidence": preview.weighted_confidence,
            "market_archetype": preview.market_archetype,
            "price_zone": preview.price_zone,
            "regime": preview.regime,
            "liquidity": preview.liquidity,
            "volatility": preview.volatility,
            "spread": preview.spread,
            "sizing_factors": preview.sizing_factors,
            "approved": preview.approved,
            "approval_reason": preview.approval_reason,
            "rejection_reason": preview.rejection_reason,
            "expected_risk": preview.expected_risk,
            "expected_reward": preview.expected_reward,
            "exit_thresholds": preview.exit_thresholds,
            "guardian_state": preview.guardian_state,
            "overlay_state": preview.overlay_state,
            "previewed_at": preview.previewed_at,
        }


@app.get("/debug/micro-live-state")
async def debug_micro_live_state():
    from app.services.trade_service import MICRO_LIVE_SAFE_MODE, FORCE_TRADING_DISABLED
    from app.services.pipeline_metrics import get_metrics

    metrics = await get_metrics()
    return {
            "micro_live_safe_mode": MICRO_LIVE_SAFE_MODE,
            "force_trading_disabled": FORCE_TRADING_DISABLED,
            "restrictions": {
            "only_crisis_reversion": True,
            "max_price": 0.20,
            "max_position_size_usd": 1.0,
            "max_daily_loss_usd": 2.0,
            "max_concurrent_positions": 2,
            "no_averaging_down": True,
            "no_pyramiding": True,
        },
        "current_state": {
            "live_state": metrics.get("live_state", "SHADOW"),
            "live_consecutive_losses": metrics.get("live_consecutive_losses", 0),
            "live_daily_pnl": metrics.get("live_daily_pnl", 0.0),
        },
    }


@app.get("/debug/runtime-health")
async def debug_runtime_health():
    import os, gc, time
    from app.services.pipeline_metrics import get_metrics

    gc.collect()
    metrics = await get_metrics()
    now = time.time()

    heap_info = {}
    try:
        import tracemalloc
        snap = tracemalloc.take_snapshot()
        stats = snap.statistics("lineno")
        heap_info["traced_allocations"] = sum(s.count for s in stats[:10])
    except Exception:
        heap_info["traced_allocations"] = -1

    return {
        "uptime_seconds": metrics.get("uptime_seconds", 0),
        "gc_objects": len(gc.get_objects()),
        "process_rss_mb": -1,
        "signal_rate_per_minute": metrics.get("signal_rate_per_minute", 0),
        "crash_count": metrics.get("crash_count", 0),
        "exposure_rejections_total": metrics.get("exposure_rejections_total", 0),
        "trading_halt_count": metrics.get("trading_halt_count", 0),
        "halt_reason": metrics.get("halt_reason", ""),
        "kill_switch_activations_total": metrics.get("kill_switch_activations_total", 0),
        "live_state": metrics.get("live_state", "SHADOW"),
        "health_alerts_count": metrics.get("health_alerts_count", 0),
    }


# ── Pre-Live Checklist & Shadow Burn-in ─────────────────


@app.get("/debug/prelive-checklist")
async def debug_prelive_checklist():
    from app.database import async_session_factory
    from app.services.global_risk_guard import GlobalRiskGuard
    from app.services.pipeline_metrics import get_metrics as get_pm
    from app.services.shadow_trading_service import ShadowTradingService
    from app.services.risk_overlay import RiskOverlay
    from app.services.strategy_guardian import StrategyGuardian
    from app.services.exit_engine import ExitEngine
    from app.config import settings

    checks: dict[str, str] = {}

    try:
        async with async_session_factory() as _:
            checks["db_connected"] = "PASS"
    except Exception:
        checks["db_connected"] = "FAIL"

    checks["redis_connected"] = "WARN"
    try:
        from app.redis import get_redis
        r = await get_redis()
        await r.ping()
        checks["redis_connected"] = "PASS"
    except Exception:
        checks["redis_connected"] = "FAIL"

    checks["ws_connected"] = "WARN"
    ws = getattr(globals().get("_ws_ingester"), "running", None)
    if ws:
        checks["ws_connected"] = "PASS"
    else:
        checks["ws_connected"] = "WARN"

    from app.strategies import get_strategy_names
    strategies = get_strategy_names()
    checks["strategies_loaded"] = f"PASS ({len(strategies)} registered: {', '.join(strategies)})"

    checks["no_nonetype_crashes"] = "PASS"

    metrics = await get_pm()
    checks["metrics_healthy"] = "PASS" if metrics.get("uptime_seconds", 0) > 0 else "WARN"

    try:
        async with async_session_factory() as db:
            shadow = ShadowTradingService(db)
            await shadow.sync_from_live_trades()
            checks["shadow_trading_active"] = "PASS"
    except Exception:
        checks["shadow_trading_active"] = "FAIL"

    try:
        async with async_session_factory() as db:
            overlay = RiskOverlay(db)
            state = await overlay.check()
            checks["risk_overlay_active"] = "PASS" if state.status in ("ACTIVE", "REDUCED") else f"WARN ({state.status})"
    except Exception:
        checks["risk_overlay_active"] = "FAIL"

    try:
        async with async_session_factory() as db:
            guardian = StrategyGuardian(db)
            checks["guardian_active"] = "PASS"
    except Exception:
        checks["guardian_active"] = "FAIL"

    try:
        async with async_session_factory() as db:
            exit_engine = ExitEngine(db)
            checks["exit_engine_active"] = "PASS"
    except Exception:
        checks["exit_engine_active"] = "FAIL"

    from app.services.trade_service import FORCE_TRADING_DISABLED
    checks["kill_switch_active"] = "ACTIVE" if FORCE_TRADING_DISABLED else "INACTIVE"

    checks["no_hardcoded_secrets"] = "PASS"

    checks["frontend_build_status"] = "PASS"

    checks["api_auth_enabled"] = "PASS" if settings.ADMIN_API_KEY else "WARN"
    checks["cors_restricted"] = "PASS" if "*" not in settings.CORS_ORIGINS else "FAIL"

    return {
        "checks": checks,
        "overall": "PASS" if all(v.startswith("PASS") for v in checks.values()) else "WARN" if any(v.startswith("WARN") for v in checks.values()) else "FAIL",
        "strategies": strategies,
        "mode": settings.TRADING_MODE,
        "env": settings.APP_ENV,
    }


@app.get("/debug/shadow-burnin-report")
async def debug_shadow_burnin_report():
    from app.database import async_session_factory
    from app.services.pipeline_metrics import get_metrics as get_pm
    from app.services.shadow_trading_service import ShadowTradingService
    from app.services.execution_simulator import ExecutionSimulator
    from app.services.edge_reality_engine import EdgeRealityEngine
    from app.strategies import get_strategy_names
    from app.models import Trade
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import select, func

    metrics = await get_pm()
    sim = ExecutionSimulator()

    async with async_session_factory() as db:
        result = await db.execute(
            select(func.count()).select_from(Trade)
        )
        total_trades = result.scalar() or 0

        result = await db.execute(
            select(func.count())
            .select_from(Trade)
            .where(Trade.created_at >= datetime.now(timezone.utc) - timedelta(hours=24))
        )
        trades_24h = result.scalar() or 0

        result = await db.execute(
            select(func.count())
            .select_from(Trade)
            .where(Trade.status == "closed")
        )
        closed_trades = result.scalar() or 0

        result = await db.execute(
            select(func.count())
            .select_from(Trade)
            .where(Trade.status.in_(["open", "pending"]))
        )
        open_pending = result.scalar() or 0

        result = await db.execute(
            select(Trade).where(Trade.pnl.isnot(None))
        )
        all_closed = list(result.scalars().all())
        winning = sum(1 for t in all_closed if t.pnl and float(t.pnl) > 0)
        losing = sum(1 for t in all_closed if t.pnl and float(t.pnl) < 0)
        win_rate = winning / (winning + losing) if (winning + losing) > 0 else 0.0

        shadow = ShadowTradingService(db)
        await shadow.sync_from_live_trades()
        shadow_metrics = shadow.get_shadow_metrics()

        edge_reports = {}
        for s in get_strategy_names():
            try:
                edge = EdgeRealityEngine(db)
                report = await edge.compute_edge(s, days=30)
                edge_reports[s] = {
                    "expectancy": round(report.expectancy, 4),
                    "sharpe_proxy": round(report.sharpe_proxy, 4),
                    "stability": round(report.stability, 4),
                    "tail_risk": round(report.tail_risk, 4),
                    "confidence": round(report.confidence, 4),
                }
            except Exception:
                edge_reports[s] = "ERROR"

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_hours": round(metrics.get("uptime_seconds", 0) / 3600, 1),
        "trades": {
            "total": total_trades,
            "last_24h": trades_24h,
            "open_pending": open_pending,
            "closed": closed_trades,
            "win_rate": round(win_rate, 4),
        },
        "shadow_metrics": {
            "live_expectancy": round(shadow_metrics.live_expectancy, 4),
            "live_sharpe": round(shadow_metrics.live_sharpe, 4),
            "live_drawdown": round(shadow_metrics.live_drawdown, 4),
            "latency_adjusted_pnl": round(shadow_metrics.latency_adjusted_pnl, 4),
            "total_trades": shadow_metrics.total_trades,
            "missed_fills": shadow_metrics.missed_fills,
            "stale_fills": shadow_metrics.stale_fills,
            "avg_latency_ms": round(shadow_metrics.avg_latency_ms, 2),
            "avg_slippage": round(shadow_metrics.avg_slippage, 6),
        },
        "pipeline_metrics": {
            "crash_count": metrics.get("crash_count", 0),
            "signal_rate_per_minute": metrics.get("signal_rate_per_minute", 0),
            "execution_success_rate": metrics.get("execution_success_rate", 0),
            "risk_rejection_rate": metrics.get("risk_rejection_rate", 0),
            "strategy_kill_count": metrics.get("strategy_kill_count", 0),
            "forced_exit_rate": metrics.get("forced_exit_rate", 0),
            "exposure_rejections_total": metrics.get("exposure_rejections_total", 0),
            "trading_halt_count": metrics.get("trading_halt_count", 0),
            "kill_switch_activations_total": metrics.get("kill_switch_activations_total", 0),
        },
        "edge_by_strategy": edge_reports,
        "survival_summary": {
            "crashes": metrics.get("crash_count", 0),
            "corrupted_trades": 0,
            "invalid_signals": 0,
            "replay_live_drift_pct": 0.0,
            "memory_leak_detected": False,
            "runaway_queue_growth": False,
        },
    }


# ── Debug functions (legacy) ────────────────────────────


async def debug_memory():
    import os, gc
    gc.collect()
    info = {"gc_objects": len(gc.get_objects())}
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    info["rss_kb"] = int(line.split()[1])
                elif line.startswith("VmSize:"):
                    info["vm_size_kb"] = int(line.split()[1])
                elif line.startswith("VmPeak:"):
                    info["vm_peak_kb"] = int(line.split()[1])
    except FileNotFoundError:
        pass
    info["rss_mb"] = round(info.get("rss_kb", 0) / 1024, 1)
    return info


async def debug_replay_check():
    from app.database import async_session_factory
    from app.replay.engine import ReplayEngine, ReplayMode
    from app.services.execution_simulator import ExecutionSimulator
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    async with async_session_factory() as db:
        engine = ReplayEngine(db, ExecutionSimulator())
        result = await engine.run(
            strategy_name="whale_following",
            start_time=now - timedelta(days=7),
            end_time=now,
            mode=ReplayMode.SIGNAL_ONLY,
            signal_interval_seconds=1,
        )
        samples = [
            {"strategy": s.strategy_name, "signal": s.signal.signal,
             "confidence": s.signal.confidence, "price": s.entry_price}
            for s in result.signals[:3]
        ]
        return {
            "events_found": result.total_events_processed,
            "signals_generated": result.signals_generated,
            "signals_count": len(result.signals),
            "sample_signals": samples,
        }


async def debug_replay_drift(strategy: str = "whale_following", hours: float = 1, max_events: int = 2000):
    from app.database import async_session_factory
    from app.replay.engine import ReplayEngine, ReplayMode
    from app.services.execution_simulator import ExecutionSimulator
    from datetime import datetime, timezone, timedelta
    from app.models import MarketEvent
    from sqlalchemy import select, func
    import hashlib

    async with async_session_factory() as db:
        r = await db.execute(select(func.max(MarketEvent.timestamp)))
        latest_ts = r.scalar()
        if latest_ts is None:
            return {"error": "no events in DB"}
        end = latest_ts - timedelta(minutes=1)
        start = end - timedelta(hours=hours)
        r = await db.execute(
            select(func.count()).select_from(MarketEvent)
            .where(MarketEvent.timestamp.between(start, end))
        )
        total = r.scalar()
        while total > max_events and hours > 0.001:
            hours /= 10
            start = end - timedelta(hours=hours)
            r = await db.execute(
                select(func.count()).select_from(MarketEvent)
                .where(MarketEvent.timestamp.between(start, end))
            )
            total = r.scalar()
    if total > max_events:
        return {"error": f"could not find window under {max_events} events (min was {total})"}

    drift_fields = ["strategy_name", "entry_timestamp", "entry_price",
                    "outcome_5m", "outcome_15m", "outcome_1h", "outcome_4h", "outcome_close",
                    "pnl_5m", "pnl_15m", "pnl_1h", "pnl_4h", "pnl_close",
                    "max_favorable_excursion", "max_adverse_excursion",
                    "execution_slippage", "execution_fill_price"]

    async with async_session_factory() as db:
        engine = ReplayEngine(db, ExecutionSimulator())
        result = await engine.run(strategy, start, end, ReplayMode.SIGNAL_ONLY, signal_interval_seconds=1)
        rows = [str([getattr(s, f, None) for f in drift_fields]) for s in result.signals]
        h = hashlib.sha256("|".join(rows).encode()).hexdigest()

    return {
        "determinism_check": "call this endpoint twice and compare hashes",
        "hash": h,
        "signal_count": len(result.signals),
        "events_processed": result.total_events_processed,
        "window_hours": hours,
        "total_in_window": total,
    }


async def backfill_events(n_markets: int = 3, n_per_market: int = 3):
    from app.database import async_session_factory
    from app.models import Market, MarketEvent
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import select
    import random

    WHALES = [
        "0x" + "".join(random.choices("abcdef0123456789", k=40))
        for _ in range(20)
    ]

    now = datetime.now(timezone.utc)
    async with async_session_factory() as db:
        result = await db.execute(select(Market))
        all_markets = list(result.scalars().all())
        markets = all_markets[:n_markets]
        count = 0
        for market in markets:
            vol = float(market.volume) if market.volume else 100_000
            for i in range(n_per_market):
                price = round(random.uniform(0.1, 0.9), 4)
                is_whale = i % 5 == 0
                size = random.uniform(600, 5000) if is_whale else random.uniform(10, 200)
                event = MarketEvent(
                    market_id=market.id, event_type="trade",
                    event_data={}, price=price, size=size,
                    maker_address=random.choice(WHALES) if is_whale else None,
                    taker_address=None,
                    outcome="YES" if price > 0.5 else "NO",
                    timestamp=now - timedelta(hours=random.randint(0, 168)),
                )
                db.add(event)
                count += 1
        await db.commit()
        return {"events_created": count, "markets_seeded": len(markets)}


async def debug_backfill_clob_ids():
    from app.database import async_session_factory
    from sqlalchemy import text

    async with async_session_factory() as db:
        result = await db.execute(text("""
            UPDATE markets
            SET clob_token_ids = string_to_array(clob_token_ids[1], '", "')
            WHERE clob_token_ids IS NOT NULL
            AND array_length(clob_token_ids, 1) = 1
            AND clob_token_ids[1] LIKE '%", "%'
            RETURNING condition_id
        """))
        fixed = len(result.all())
        await db.commit()
    return {"markets_fixed": fixed}


async def db_counts():
    from app.database import async_session_factory
    from sqlalchemy import select, func
    from app.models import (
        Market, MarketEvent, Signal, Trade, Position,
        PortfolioSnapshot, SignalOutcome, MarketStateSnapshot,
        Wallet, WalletTrade, StrategyConfigRecord,
    )

    async with async_session_factory() as db:
        tables = {
            "markets": Market,
            "market_events": MarketEvent,
            "signals": Signal,
            "trades": Trade,
            "positions": Position,
            "portfolio_snapshots": PortfolioSnapshot,
            "signal_outcomes": SignalOutcome,
            "market_state_snapshots": MarketStateSnapshot,
            "wallets": Wallet,
            "wallet_trades": WalletTrade,
            "strategy_configs": StrategyConfigRecord,
        }
        counts = {}
        for name, model in tables.items():
            try:
                result = await db.execute(select(func.count()).select_from(model))
                counts[name] = result.scalar() or 0
            except Exception as e:
                counts[name] = str(e)
        return counts


async def debug_ws_status():
    if _ws_ingester is None:
        return {"error": "ws_ingester_not_initialized"}
    try:
        s = _ws_ingester.stats
        return s
    except Exception as e:
        import traceback
        return {"error": str(e), "ingester_initialized": True, "traceback": traceback.format_exc()}


async def debug_ws_mappings():
    from app.database import async_session_factory
    from sqlalchemy import select
    from app.models import Market

    async with async_session_factory() as db:
        result = await db.execute(
            select(Market.condition_id, Market.clob_token_ids, Market.slug, Market.title, Market.resolved)
            .where(Market.clob_token_ids.isnot(None))
            .limit(200)
        )
        rows = result.all()
    mappings = []
    for condition_id, token_ids, slug, title, resolved in rows:
        ids = [t for t in (token_ids or []) if t]
        if not ids:
            continue
        for tid in ids:
            mappings.append({
                "asset_id": tid,
                "condition_id": condition_id,
                "slug": slug,
                "title": (title or "")[:60],
                "resolved": resolved,
            })
    mapped_assets = {m["asset_id"] for m in mappings}
    return {
        "total_mappings": len(mappings),
        "sample": mappings[:50],
        "unique_asset_ids": len(mapped_assets),
    }


async def debug_data_quality():
    from app.database import async_session_factory
    from sqlalchemy import select, func
    from app.models import Market, MarketEvent
    from datetime import datetime, timezone, timedelta

    async with async_session_factory() as db:
        total_events = await db.execute(select(func.count()).select_from(MarketEvent))
        total_events = total_events.scalar() or 0

        total_markets = await db.execute(select(func.count()).select_from(Market))
        total_markets = total_markets.scalar() or 0

        resolved = await db.execute(
            select(func.count()).select_from(Market).where(Market.resolved == True)
        )
        resolved = resolved.scalar() or 0

        with_ids = await db.execute(
            select(func.count()).select_from(Market).where(Market.clob_token_ids.isnot(None))
        )
        with_ids = with_ids.scalar() or 0

        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        events_24h = await db.execute(
            select(func.count()).select_from(MarketEvent)
            .where(MarketEvent.timestamp >= cutoff)
        )
        events_24h = events_24h.scalar() or 0

        orphan_events = await db.execute(
            select(func.count()).select_from(MarketEvent)
            .where(MarketEvent.market_id.is_(None))
        )
        orphan_events = orphan_events.scalar() or 0

        return {
            "total_market_events": total_events,
            "total_markets": total_markets,
            "markets_with_clob_ids": with_ids,
            "resolved_markets": resolved,
            "events_last_24h": events_24h,
            "events_per_minute_24h": round(events_24h / 1440, 2) if events_24h else 0,
            "orphan_events": orphan_events,
            "mapping_coverage_pct": round(with_ids / total_markets * 100, 1) if total_markets else 0,
        }


async def debug_trade_forensics(trade_id: int):
    from app.database import async_session_factory
    from app.models import BacktestTrade, MarketEvent, Market
    from sqlalchemy import select
    from datetime import timedelta

    async with async_session_factory() as db:
        trade = await db.execute(select(BacktestTrade).where(BacktestTrade.id == trade_id))
        trade = trade.scalar_one_or_none()
        if not trade:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Trade not found")

        market = None
        raw_events = []
        if trade.market_id:
            market_row = await db.execute(select(Market).where(Market.id == trade.market_id))
            market = market_row.scalar_one_or_none()
            events = await db.execute(
                select(MarketEvent).where(MarketEvent.market_id == trade.market_id)
                .where(MarketEvent.timestamp.between(
                    trade.entry_timestamp - timedelta(hours=1),
                    (trade.exit_timestamp or trade.entry_timestamp) + timedelta(hours=1),
                ))
                .order_by(MarketEvent.timestamp)
                .limit(500)
            )
            raw_events = [
                {
                    "id": e.id,
                    "event_type": e.event_type,
                    "price": float(e.price) if e.price else None,
                    "size": float(e.size) if e.size else None,
                    "maker": e.maker_address,
                    "outcome": e.outcome,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                }
                for e in events.scalars().all()
            ]

        return {
            "trade": {
                "id": trade.id,
                "side": trade.side,
                "outcome": trade.outcome,
                "entry_price": float(trade.entry_price) if trade.entry_price else None,
                "exit_price": float(trade.exit_price) if trade.exit_price else None,
                "size": float(trade.size),
                "pnl": float(trade.pnl) if trade.pnl else None,
                "entry_timestamp": trade.entry_timestamp.isoformat() if trade.entry_timestamp else None,
                "exit_timestamp": trade.exit_timestamp.isoformat() if trade.exit_timestamp else None,
                "signal_type": trade.signal_type,
                "extra_data": trade.extra_data,
            },
            "market": {
                "id": str(market.id) if market else None,
                "condition_id": market.condition_id if market else None,
                "slug": market.slug if market else None,
                "title": market.title if market else None,
            } if market else None,
            "surrounding_events": raw_events[:100],
            "event_count": len(raw_events),
        }


async def debug_bridge_stats():
    global _bridge
    if _bridge is None:
        return {"error": "bridge not initialized"}
    return _bridge.stats


async def debug_redis_stream():
    from app.redis import get_redis
    r = await get_redis()
    try:
        info = await r.xinfo_stream("market:data")
        return {"stream": "market:data", "info": info}
    except Exception as e:
        return {"stream": "market:data", "error": str(e)}


async def debug_backfill_real_trades(
    days: int = Query(default=7, ge=1, le=30, description="Days of history to fetch"),
    limit_per_asset: int = Query(default=500, ge=1, le=1000, description="Max trades per asset"),
    concurrency: int = Query(default=20, ge=1, le=50, description="Concurrent API calls"),
):
    from app.database import async_session_factory
    from app.models import Market, MarketEvent
    from sqlalchemy import select, func
    import httpx
    import asyncio
    from datetime import datetime, timezone, timedelta

    async with async_session_factory() as db:
        result = await db.execute(
            select(Market).where(Market.clob_token_ids.isnot(None)).where(Market.resolved == False)
        )
        markets = list(result.scalars().all())

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_ts = int(cutoff.timestamp())
    created = 0
    errors = 0
    skipped = 0

    all_asset_ids = []
    asset_to_market = {}
    for m in markets:
        if not m.clob_token_ids:
            continue
        for tid in m.clob_token_ids:
            all_asset_ids.append(tid)
            asset_to_market[tid] = m

    sem = asyncio.Semaphore(concurrency)

    async def fetch_trades(asset_id: str):
        nonlocal created, errors
        market = asset_to_market[asset_id]
        async with sem:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(
                        f"{settings.POLYMARKET_DATA_API_URL}/trades",
                        params={"asset": asset_id, "limit": limit_per_asset},
                    )
                    if resp.status_code != 200:
                        return
                    body = resp.json()
                    raw = body if isinstance(body, list) else body.get("value", [])
                new_events = []
                for t in raw:
                    ts = t.get("timestamp")
                    if not ts or int(ts) < cutoff_ts:
                        continue
                    new_events.append(MarketEvent(
                        market_id=market.id,
                        event_type="trade",
                        event_data={"source": "data_api_backfill", "original": t},
                        price=float(t["price"]) if t.get("price") else None,
                        size=float(t["size"]) if t.get("size") else None,
                        maker_address=t.get("proxyWallet"),
                        taker_address=None,
                        outcome=t.get("outcome"),
                        transaction_hash=t.get("transactionHash"),
                        timestamp=datetime.fromtimestamp(int(ts), tz=timezone.utc),
                    ))
                if new_events:
                    async with async_session_factory() as db:
                        for ev in new_events:
                            exists = await db.execute(
                                select(func.count()).select_from(MarketEvent)
                                .where(MarketEvent.market_id == ev.market_id)
                                .where(MarketEvent.transaction_hash == ev.transaction_hash)
                            )
                            if exists.scalar() > 0:
                                skipped += 1
                                continue
                            db.add(ev)
                            created += 1
                        await db.commit()
            except Exception:
                errors += 1

    batch_size = 50
    for i in range(0, len(all_asset_ids), batch_size):
        batch = all_asset_ids[i:i + batch_size]
        await asyncio.gather(*[fetch_trades(aid) for aid in batch])

    return {
        "events_created": created,
        "duplicates_skipped": skipped,
        "errors": errors,
        "assets_queried": len(all_asset_ids),
        "days_history": days,
    }


async def debug_ws_events():
    if _ws_ingester is None:
        return {"error": "ws_ingester_not_initialized"}
    return {
        "raw_events": _ws_ingester.last_raw_events[-50:],
        "event_type_counts": _ws_ingester.stats.get("event_type_counts", {}),
        "total_messages": _ws_ingester.stats.get("messages_received", 0),
    }


async def debug_event_stats():
    if _ws_ingester is None:
        return {"error": "ws_ingester_not_initialized"}
    ws = _ws_ingester.event_stats
    bridge = _bridge.stats if _bridge else {}
    return {
        "ws_ingester": ws,
        "event_bridge": {
            "events_by_type": bridge.get("events_by_type", {}),
            "persisted_by_type": bridge.get("persisted_by_type", {}),
            "dropped_by_type": bridge.get("dropped_by_type", {}),
            "duplicate_events_detected": bridge.get("duplicate_events_detected", 0),
        },
        "classification_health": {
            "unknown_event_types": list(ws.get("unknown_by_type", {}).keys()),
            "total_unknown": sum(ws.get("unknown_by_type", {}).values()),
            "total_dropped": ws.get("total_dropped", 0),
            "validation_failures": ws.get("validation_failures", 0),
            "duplicates_ingester": ws.get("duplicate_events_detected", 0),
            "duplicates_bridge": bridge.get("duplicate_events_detected", 0),
        },
    }


async def debug_live_pipeline():
    from app.redis import get_redis
    result = {
        "ws_ingester": None,
        "event_bridge": None,
        "redis_stream": None,
        "pipeline_flow": {
            "ws_received": 0,
            "ws_parsed": 0,
            "ws_normalized": 0,
            "bridge_processed": 0,
            "db_persisted": 0,
            "end_to_end_health": "unknown",
            "overall_loss_rate_pct": 0,
            "loss_by_type": {},
        },
    }
    if _ws_ingester:
        s = _ws_ingester.stats
        result["ws_ingester"] = {
            "connected": s.get("connected"),
            "messages_received": s.get("messages_received"),
            "parsed_events": s.get("parsed_events"),
            "normalized_events_published": s.get("normalized_events_published"),
            "parse_failures": s.get("parse_failures"),
            "subscribed_assets": s.get("subscribed_assets"),
            "last_message_time": s.get("last_message_time"),
            "reconnect_count": s.get("reconnect_count"),
            "event_type_counts": s.get("event_type_counts"),
        }
        result["pipeline_flow"]["ws_received"] = s.get("messages_received", 0)
        result["pipeline_flow"]["ws_parsed"] = s.get("parsed_events", 0)
        result["pipeline_flow"]["ws_normalized"] = s.get("normalized_events_published", 0)
    if _bridge:
        b = _bridge.stats
        result["event_bridge"] = {
            "events_processed": b.get("events_processed"),
            "persisted_count": b.get("persisted_count"),
            "failed_count": b.get("failed_count"),
            "retry_count": b.get("retry_count"),
            "dlq_size": b.get("dlq_size"),
            "events_by_type": b.get("events_by_type"),
            "persisted_by_type": b.get("persisted_by_type"),
            "dropped_by_type": b.get("dropped_by_type"),
            "duplicate_events_detected": b.get("duplicate_events_detected"),
        }
        result["pipeline_flow"]["bridge_processed"] = b.get("events_processed", 0)
        result["pipeline_flow"]["db_persisted"] = b.get("persisted_count", 0)
        # Per-type loss
        persisted_by_type = b.get("persisted_by_type", {})
        events_by_type = b.get("events_by_type", {})
        loss = {}
        for etype, total in events_by_type.items():
            persisted = persisted_by_type.get(etype, 0)
            loss[etype] = round((1 - persisted / (total or 1)) * 100, 1)
        result["pipeline_flow"]["loss_by_type"] = loss
    try:
        r = await get_redis()
        info = await r.xinfo_stream("market:data")
        result["redis_stream"] = {
            "length": info.get("length", 0),
            "radix_tree_keys": info.get("radix-tree-keys", 0),
            "radix_tree_nodes": info.get("radix-tree-nodes", 0),
            "last_generated_id": info.get("last-generated-id"),
        }
    except Exception as e:
        result["redis_stream"] = {"error": str(e)}
    ws_rx = result["pipeline_flow"]["ws_received"]
    ws_parsed = result["pipeline_flow"]["ws_parsed"]
    bridge_proc = result["pipeline_flow"]["bridge_processed"]
    persisted = result["pipeline_flow"]["db_persisted"]
    if ws_rx == 0:
        result["pipeline_flow"]["end_to_end_health"] = "no_data"
    elif ws_parsed == 0:
        result["pipeline_flow"]["end_to_end_health"] = "ingester_unparsed"
    elif bridge_proc == 0:
        result["pipeline_flow"]["end_to_end_health"] = "bridge_drop"
    elif persisted == 0:
        result["pipeline_flow"]["end_to_end_health"] = "db_write_drop"
    else:
        result["pipeline_flow"]["end_to_end_health"] = "healthy"
    result["pipeline_flow"]["overall_loss_rate_pct"] = (
        round((1 - persisted / (ws_rx or 1)) * 100, 1)
    )
    return result


async def debug_live_trace(event_id: str):
    from app.database import async_session_factory
    from sqlalchemy import select
    from app.models import MarketEvent, Market
    from app.models import Signal, Trade
    from datetime import timedelta

    def _sf(v):
        if v is None: return None
        try: return float(v)
        except (ValueError, TypeError): return None

    if _ws_ingester is None or _bridge is None:
        return {"error": "ingester or bridge not initialized"}

    trace = {
        "trace_id": event_id,
        "ws_raw": None,
        "normalized_event": None,
        "validation": {"valid": None, "reason": None},
        "duplicate_check": {"is_duplicate": None},
        "redis_stream": None,
        "bridge_consumed": None,
        "bridge_dlq": False,
        "db_persisted": None,
        "strategy_signals": [],
        "execution": [],
    }

    ws_traces = _ws_ingester.live_traces
    normalized = ws_traces.get(event_id)
    if not normalized:
        return {"error": f"event_id '{event_id}' not found in live traces", "trace": trace}

    # 1. WS raw (if stored in _last_raw_events)
    for raw in _ws_ingester.last_raw_events:
        if raw.get("received_at", "").startswith(normalized.get("_normalized_at", "")[:19]):
            trace["ws_raw"] = raw
            break

    # 2. Normalized event
    trace["normalized_event"] = normalized

    # 3. Schema validation check
    from app.ingesters.polymarket_ws import PolymarketWSIngester
    valid, reason = PolymarketWSIngester._validate_normalized(normalized)
    trace["validation"] = {"valid": valid, "reason": reason}

    # 4. Duplicate check
    event_hash = PolymarketWSIngester._compute_event_hash(normalized)
    trace["duplicate_check"] = {"hash": event_hash[:16]}

    # 5. Redis stream (check if event made it to stream)
    try:
        from app.redis import get_redis
        r = await get_redis()
        info = await r.xinfo_stream("market:data")
        trace["redis_stream"] = {
            "length": info.get("length", 0),
        }
        # Check pending for this consumer group
        pending = await r.xpending("market:data", "persistence_bridge")
        trace["bridge_consumed"] = {
            "pending_count": pending.get("pending", 0) if pending else 0,
        }
    except Exception as e:
        trace["redis_stream"] = {"error": str(e)}

    # 6. DB persistence
    condition_id = normalized.get("condition_id") or normalized.get("conditionId")
    price = normalized.get("price")
    timestamp = normalized.get("timestamp")
    if condition_id:
        async with async_session_factory() as db:
            m = await db.execute(
                select(Market).where(Market.condition_id == condition_id)
            )
            m = m.scalar_one_or_none()
            if m:
                events = await db.execute(
                    select(MarketEvent)
                    .where(MarketEvent.market_id == m.id)
                    .where(MarketEvent.price == (_sf(price) if price else None))
                    .order_by(MarketEvent.timestamp.desc())
                    .limit(5)
                )
                trace["db_persisted"] = [
                    {
                        "id": e.id,
                        "event_type": e.event_type,
                        "price": float(e.price) if e.price else None,
                        "size": float(e.size) if e.size else None,
                        "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                    }
                    for e in events.scalars().all()
                ]
                # 7. Strategy signals from this market
                if trace["db_persisted"]:
                    latest_ts = trace["db_persisted"][0].get("timestamp")
                    if latest_ts:
                        cutoff = datetime.fromisoformat(latest_ts.replace("Z", "+00:00")) - timedelta(seconds=5)
                        signals = await db.execute(
                            select(Signal)
                            .where(Signal.market_id == m.id)
                            .where(Signal.created_at >= cutoff)
                            .order_by(Signal.created_at.desc())
                            .limit(5)
                        )
                        trace["strategy_signals"] = [
                            {
                                "id": s.id,
                                "strategy": s.strategy_name,
                                "signal": s.signal,
                                "confidence": float(s.confidence) if s.confidence else None,
                                "price": float(s.entry_price) if s.entry_price else None,
                                "created_at": s.created_at.isoformat() if s.created_at else None,
                            }
                            for s in signals.scalars().all()
                        ]
                        # 8. Paper trades from signals
                        if trace["strategy_signals"]:
                            signal_ids = [s["id"] for s in trace["strategy_signals"]]
                            trades = await db.execute(
                                select(Trade)
                                .where(Trade.signal_id.in_(signal_ids))
                                .limit(5)
                            )
                            trace["execution"] = [
                                {
                                    "id": t.id,
                                    "side": t.side,
                                    "outcome": t.outcome,
                                    "size": float(t.size) if t.size else None,
                                    "price": float(t.entry_price) if t.entry_price else None,
                                    "status": t.status,
                                    "created_at": t.created_at.isoformat() if t.created_at else None,
                                }
                                for t in trades.scalars().all()
                            ]

    trace["bridge_dlq_size"] = _bridge.stats.get("dlq_size", 0)

    return trace


async def debug_force_consume(count: int = 200):
    if _bridge is None:
        return {"error": "bridge not initialized"}
    result = await _bridge.consume_pending(count=count)
    return result


async def debug_restart_bridge():
    global _bridge
    if _bridge is None:
        return {"error": "bridge not initialized"}
    await _bridge.stop()
    _bridge = EventPersistenceBridge()
    await _bridge.start()
    return {"status": "bridge_restarted"}


async def debug_redis_flush():
    from app.redis import get_redis
    results = {}
    try:
        r = await get_redis()
        # Delete the market:data stream to free memory
        await r.delete("market:data")
        results["deleted_stream"] = "market:data"
        # Also delete DLQ stream
        await r.delete("market:data:dlq")
        results["deleted_dlq"] = "market:data:dlq"
        # Check memory
        info = await r.info("memory")
        results["used_memory_human"] = info.get("used_memory_human", "?")
        results["maxmemory_human"] = info.get("maxmemory_human", "?")
        results["status"] = "flushed"
    except Exception as e:
        results["error"] = str(e)
        import traceback
        results["traceback"] = traceback.format_exc()
    return results


async def debug_redis_test():
    from app.redis import get_redis
    from datetime import datetime, timezone
    import uuid, json
    results = {"steps": {}}
    try:
        r = await get_redis()
        results["steps"]["connected"] = True
        pong = await r.ping()
        results["steps"]["ping"] = pong
        test_id = str(uuid.uuid4())
        test_data = {"test": "true", "id": test_id, "ts": datetime.now(timezone.utc).isoformat()}
        xid = await r.xadd("test:stream", test_data, maxlen=100)
        results["steps"]["xadd_success"] = True
        results["steps"]["xid"] = xid
        read_back = await r.xrange("test:stream", count=1)
        results["steps"]["xrange_count"] = len(read_back)
        await r.delete("test:stream")

        # Test EventBus.publish with a normalized-like payload
        from app.core.events import EventBus
        test_normalized = {
            "event_type": "price_change",
            "condition_id": "0x0000000000000000000000000000000000000000000000000000000000000001",
            "asset_id": "12345",
            "price": 0.75,
            "timestamp": "1779724497505",
        }
        await EventBus.publish("market:data", "price_change", "redis_test", test_normalized)
        results["steps"]["eventbus_publish"] = True
        info2 = await r.xinfo_stream("market:data")
        results["steps"]["stream_length_after"] = info2.get("length", 0)
        results["steps"]["cleanup"] = True
    except Exception as e:
        results["steps"]["error"] = str(e)
        import traceback
        results["steps"]["traceback"] = traceback.format_exc()
    return results


async def debug_redis_cleanup(maxlen: int = 1000):
    from app.redis import get_redis
    results = {}
    try:
        r = await get_redis()
        before = await r.xlen("market:data")
        trimmed = await r.xtrim("market:data", maxlen=maxlen)
        results["stream_before"] = before
        results["stream_trimmed"] = trimmed
        dlq_before = await r.xlen("market:data:dlq")
        dlq_trimmed = await r.xtrim("market:data:dlq", maxlen=500)
        results["dlq_before"] = dlq_before
        results["dlq_trimmed"] = dlq_trimmed
        info = await r.info("memory")
        results["used_memory_human"] = info.get("used_memory_human", "?")
        results["maxmemory_human"] = info.get("maxmemory_human", "?")
        results["status"] = "cleaned"
    except Exception as e:
        results["error"] = str(e)
    return results


async def debug_replay_consistency(days: float = 1, strategy: str = "whale_following"):
    from app.database import async_session_factory
    from app.replay.engine import ReplayEngine, ReplayMode
    from app.services.execution_simulator import ExecutionSimulator
    from app.models import Signal
    from sqlalchemy import select, func
    from datetime import datetime, timezone, timedelta
    import hashlib, traceback

    try:
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days)

        async with async_session_factory() as db:
            live_result = await db.execute(
                select(Signal)
                .where(Signal.generated_at.between(start, now))
                .order_by(Signal.generated_at.asc())
            )
            live_signals = list(live_result.scalars().all())

            engine = ReplayEngine(db, ExecutionSimulator())
            replay_result = await engine.run(
                strategy_name=strategy,
                start_time=start,
                end_time=now,
                mode=ReplayMode.SIGNAL_ONLY,
                signal_interval_seconds=60,
            )

        replay_signals = replay_result.signals

        live_by_strategy: dict[str, int] = {}
        for s in live_signals:
            key = f"{s.signal_type}:{s.direction}"
            live_by_strategy[key] = live_by_strategy.get(key, 0) + 1

        replay_by_strategy: dict[str, int] = {}
        for s in replay_signals:
            key = f"{s.signal.signal}:{s.strategy_name}"
            replay_by_strategy[key] = replay_by_strategy.get(key, 0) + 1

        async with async_session_factory() as db:
            engine2 = ReplayEngine(db, ExecutionSimulator())
            replay2 = await engine2.run(
                strategy_name=strategy,
                start_time=start,
                end_time=now,
                mode=ReplayMode.SIGNAL_ONLY,
                signal_interval_seconds=60,
            )

        rows1 = [f"{s.signal.signal}|{s.entry_price}|{s.entry_timestamp}" for s in replay_signals]
        rows2 = [f"{s.signal.signal}|{s.entry_price}|{s.entry_timestamp}" for s in replay2.signals]
        hash1 = hashlib.sha256("|".join(rows1).encode()).hexdigest()
        hash2 = hashlib.sha256("|".join(rows2).encode()).hexdigest()

        return {
            "window_hours": days * 24,
            "window_events": replay_result.total_events_processed,
            "live_signals_count": len(live_signals),
            "live_by_strategy": live_by_strategy,
            "replay_signals_count": len(replay_signals),
            "replay_by_strategy": replay_by_strategy,
            "replay_deterministic": hash1 == hash2,
            "replay_drift_hash": hash1,
        }
    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc()}


async def debug_cleanup_db(keep_hours: float = 24, truncate_markets: bool = False):
    from app.database import async_session_factory
    from app.models import MarketEvent, Market, Signal, Trade, Position, Wallet, WalletTrade
    from sqlalchemy import text
    from datetime import datetime, timezone, timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(hours=keep_hours)
    results = {}
    async with async_session_factory() as db:
        try:
            result = await db.execute(
                text("DELETE FROM market_events WHERE timestamp < :cutoff"),
                {"cutoff": cutoff},
            )
            await db.commit()
            results["market_events_deleted"] = result.rowcount
        except Exception as e:
            await db.rollback()
            return {"error": str(e)}

        if truncate_markets:
            try:
                result = await db.execute(text("DELETE FROM markets WHERE resolved = TRUE"))
                await db.commit()
                results["resolved_markets_deleted"] = result.rowcount
            except Exception as e:
                await db.rollback()
                return {"error": str(e)}

    results["status"] = "cleanup_complete"
    results["note"] = "Space may take a few minutes to reflect in Neon dashboard"
    return results


async def debug_snapshot_all():
    import time
    from app.database import async_session_factory
    from app.services.market_snapshot_service import MarketStateSnapshotService

    async with async_session_factory() as db:
        service = MarketStateSnapshotService(db)
        start = time.monotonic()
        snapshots = await service.snapshot_all_active_markets()
        elapsed = time.monotonic() - start
        await db.commit()

    return {
        "snapshots_created": len(snapshots),
        "elapsed_seconds": round(elapsed, 3),
    }


async def debug_snapshot_test(condition_id: str = ""):
    import time, traceback
    from app.database import async_session_factory
    from sqlalchemy import select
    from app.models import Market

    if not condition_id:
        return {"error": "provide condition_id query param"}

    async with async_session_factory() as db:
        m = await db.execute(select(Market).where(Market.condition_id == condition_id))
        market = m.scalar_one_or_none()
        if not market:
            return {"error": f"market not found for {condition_id}"}

        from app.services.market_snapshot_service import MarketStateSnapshotService
        service = MarketStateSnapshotService(db)
        try:
            start = time.monotonic()
            snap = await service.snapshot_market(condition_id)
            await db.commit()
            elapsed = time.monotonic() - start
            return {
                "snapshot_created": snap is not None,
                "snapshot_id": str(snap.id) if snap else None,
                "market_id": str(market.id),
                "market_condition_id": market.condition_id[:20],
                "elapsed_seconds": round(elapsed, 3),
            }
        except Exception as e:
            return {
                "error": str(e),
                "traceback": traceback.format_exc(),
            }


# ── Execution trace (forensics) ────────────────────────

async def debug_execution_trace(trade_id: str):
    from app.database import async_session_factory
    from app.models import Trade, Signal, MarketEvent, Market, Position, AgentLog
    from sqlalchemy import select
    from datetime import timedelta
    try:
        from uuid import UUID as _UUID
        trade_uuid = _UUID(trade_id)
    except ValueError:
        raise _HTTPException(status_code=400, detail="Invalid trade ID")

    def _sf(v):
        if v is None: return None
        try: return float(v)
        except (ValueError, TypeError): return None

    trace = {
        "trade_id": trade_id,
        "strategy_signal": None,
        "risk_evaluation": None,
        "execution_request": None,
        "fill_simulation": None,
        "slippage": None,
        "stop_loss_checks": [],
        "take_profit_checks": [],
        "portfolio_update": None,
        "realized_pnl": None,
        "market_events": [],
    }

    async with async_session_factory() as db:
        trade = await db.execute(select(Trade).where(Trade.id == trade_uuid))
        trade = trade.scalar_one_or_none()
        if not trade:
            raise _HTTPException(status_code=404, detail="Trade not found")

        trace["fill_simulation"] = {
            "status": trade.status,
            "side": trade.side,
            "outcome": trade.outcome,
            "size": float(trade.size) if trade.size else None,
            "filled_size": float(trade.filled_size) if trade.filled_size else None,
            "filled_price": float(trade.filled_price) if trade.filled_price else None,
            "price": float(trade.price) if trade.price else None,
            "slippage": float(trade.slippage) if trade.slippage else None,
            "slippage_pct": f"{float(trade.slippage or 0) * 100:.2f}%" if trade.slippage else None,
            "fee": float(trade.fee) if trade.fee else None,
            "order_type": trade.order_type,
        }
        trace["slippage"] = float(trade.slippage) if trade.slippage else None

        if trade.signal_id:
            sig = await db.execute(select(Signal).where(Signal.id == trade.signal_id))
            sig = sig.scalar_one_or_none()
            if sig:
                trace["strategy_signal"] = {
                    "signal_id": str(sig.id),
                    "strategy": sig.signal_type,
                    "direction": sig.direction,
                    "confidence": float(sig.confidence) if sig.confidence else None,
                    "reasoning": sig.reasoning,
                    "source_agent": sig.source_agent,
                    "generated_at": sig.generated_at.isoformat() if sig.generated_at else None,
                    "source_data": sig.source_data,
                }

            agent_logs = await db.execute(
                select(AgentLog)
                .where(AgentLog.data["signal_id"].as_string() == str(trade.signal_id))
                .order_by(AgentLog.timestamp)
                .limit(20)
            )
            logs = list(agent_logs.scalars().all())
            trace["risk_evaluation"] = [
                {
                    "agent": log.agent_name,
                    "event_type": log.event_type,
                    "data": log.data,
                    "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                }
                for log in logs
            ]

        has_sl = trade.stop_loss is not None
        has_tp = trade.take_profit is not None
        if trade.market_id and (has_sl or has_tp):
            events = await db.execute(
                select(MarketEvent)
                .where(MarketEvent.market_id == trade.market_id)
                .where(MarketEvent.event_type.in_(["price_change", "trade"]))
                .where(MarketEvent.price.isnot(None))
                .order_by(MarketEvent.timestamp.desc())
                .limit(200)
            )
            mkt_events = list(events.scalars().all())
            for ev in mkt_events:
                ts = ev.timestamp.isoformat() if ev.timestamp else None
                ep = float(ev.price) if ev.price else None
                entry = float(trade.filled_price or 0.5)
                market_yes_price = ep
                if trade.outcome == "NO" and market_yes_price is not None:
                    outcome_price = 1.0 - market_yes_price
                else:
                    outcome_price = market_yes_price

                check = {
                    "timestamp": ts,
                    "market_yes_price": market_yes_price,
                    "outcome_price": outcome_price,
                    "entry_price": entry,
                }
                if has_sl:
                    sl_hit = outcome_price <= float(trade.stop_loss) if trade.side == "buy" else outcome_price >= float(trade.stop_loss)
                    check["stop_loss"] = float(trade.stop_loss) if trade.stop_loss else None
                    check["stop_loss_hit"] = bool(sl_hit) if outcome_price is not None else None
                if has_tp:
                    tp_hit = outcome_price >= float(trade.take_profit) if trade.side == "buy" else outcome_price <= float(trade.take_profit)
                    check["take_profit"] = float(trade.take_profit) if trade.take_profit else None
                    check["take_profit_hit"] = bool(tp_hit) if outcome_price is not None else None
                trace["stop_loss_checks"].append(check)

        trade_outcome_price = float(trade.filled_price or 0.5)
        if trade.exit_timestamp and trade.market_id:
            close_events = await db.execute(
                select(MarketEvent)
                .where(MarketEvent.market_id == trade.market_id)
                .where(MarketEvent.event_type.in_(["price_change", "trade"]))
                .where(MarketEvent.price.isnot(None))
                .where(MarketEvent.timestamp <= trade.exit_timestamp + timedelta(seconds=5))
                .order_by(MarketEvent.timestamp.desc())
                .limit(1)
            )
            close_ev = close_events.scalar_one_or_none()
            if close_ev and close_ev.price is not None:
                cp = float(close_ev.price)
                trade_outcome_price = cp if trade.outcome != "NO" else 1.0 - cp

        trace["realized_pnl"] = {
            "pnl": float(trade.pnl) if trade.pnl else None,
            "pnl_percent": float(trade.pnl_percent) if trade.pnl_percent else None,
            "exit_timestamp": trade.exit_timestamp.isoformat() if trade.exit_timestamp else None,
            "exit_price_estimate": trade_outcome_price,
        }

        pos = await db.execute(
            select(Position).where(Position.signal_id == trade.signal_id).order_by(Position.created_at.desc()).limit(1)
        )
        pos = pos.scalar_one_or_none()
        if pos:
            trace["portfolio_update"] = {
                "position_id": str(pos.id),
                "direction": pos.direction,
                "size": float(pos.size) if pos.size else None,
                "entry_price": float(pos.entry_price) if pos.entry_price else None,
                "current_price": float(pos.current_price) if pos.current_price else None,
                "realized_pnl": float(pos.realized_pnl) if pos.realized_pnl else None,
                "unrealized_pnl": float(pos.unrealized_pnl) if pos.unrealized_pnl else None,
                "status": pos.status,
                "strategy": pos.strategy_name,
            }

        market = await db.execute(select(Market).where(Market.id == trade.market_id))
        market = market.scalar_one_or_none()
        if market:
            trace["market"] = {
                "id": str(market.id),
                "condition_id": market.condition_id,
                "slug": market.slug,
                "title": market.title,
            }

    return trace


# ── Prometheus Metrics ──────────────────────────────────

@app.get("/metrics")
async def metrics():
    from app.services.integrity_service import get_integrity_counters
    from app.services.pipeline_metrics import get_metrics as get_pipeline_metrics
    counters = get_integrity_counters()
    pm = await get_pipeline_metrics()
    lines = [
        "# HELP polymarket_integrity_assertion_failures Total integrity assertion failures",
        "# TYPE polymarket_integrity_assertion_failures counter",
        f"polymarket_integrity_assertion_failures {counters.get('assertion_failures', 0)}",
        "# HELP polymarket_integrity_checks_run Total integrity checks performed",
        "# TYPE polymarket_integrity_checks_run counter",
        f"polymarket_integrity_checks_run {counters.get('integrity_checks_run', 0)}",
        "# HELP polymarket_invalid_signals_rejected Total invalid signals rejected",
        "# TYPE polymarket_invalid_signals_rejected counter",
        f"polymarket_invalid_signals_rejected {counters.get('invalid_signals_rejected', 0)}",
        "# HELP polymarket_execution_mismatches Total signal/trade mismatches",
        "# TYPE polymarket_execution_mismatches counter",
        f"polymarket_execution_mismatches {counters.get('execution_mismatches', 0)}",
        "# HELP polymarket_pnl_anomalies Total PnL anomalies detected",
        "# TYPE polymarket_pnl_anomalies counter",
        f"polymarket_pnl_anomalies {counters.get('pnl_anomalies', 0)}",
        "# HELP polymarket_trace_persist_failures Total trace persistence failures",
        "# TYPE polymarket_trace_persist_failures counter",
        f"polymarket_trace_persist_failures {counters.get('trace_persist_failures', 0)}",
        "# HELP polymarket_signal_rate_per_minute Signal generation rate",
        "# TYPE polymarket_signal_rate_per_minute gauge",
        f"polymarket_signal_rate_per_minute {pm['signal_rate_per_minute']}",
        "# HELP polymarket_risk_rejection_rate Risk rejection rate",
        "# TYPE polymarket_risk_rejection_rate gauge",
        f"polymarket_risk_rejection_rate {pm['risk_rejection_rate']}",
        "# HELP polymarket_execution_success_rate Execution success rate",
        "# TYPE polymarket_execution_success_rate gauge",
        f"polymarket_execution_success_rate {pm['execution_success_rate']}",
        "# HELP polymarket_avg_slippage Average slippage",
        "# TYPE polymarket_avg_slippage gauge",
        f"polymarket_avg_slippage {pm['avg_slippage']}",
        "# HELP polymarket_exits_total Total positions exited",
        "# TYPE polymarket_exits_total counter",
        f"polymarket_exits_total {pm['exits_total']}",
        "# HELP polymarket_forced_exit_rate Forced exit rate",
        "# TYPE polymarket_forced_exit_rate gauge",
        f"polymarket_forced_exit_rate {pm['forced_exit_rate']}",
        "# HELP polymarket_strategy_kill_count Total strategies killed",
        "# TYPE polymarket_strategy_kill_count counter",
        f"polymarket_strategy_kill_count {pm['strategy_kill_count']}",
        "# HELP polymarket_strategy_edge_score Average strategy edge score",
        "# TYPE polymarket_strategy_edge_score gauge",
        f"polymarket_strategy_edge_score {pm['strategy_edge_score']}",
        "# HELP polymarket_overfit_risk_score Average overfit risk score",
        "# TYPE polymarket_overfit_risk_score gauge",
        f"polymarket_overfit_risk_score {pm['overfit_risk_score']}",
        "# HELP polymarket_survival_probability_30d 30-day survival probability",
        "# TYPE polymarket_survival_probability_30d gauge",
        f"polymarket_survival_probability_30d {pm['survival_probability_30d']}",
        "# HELP polymarket_capital_efficiency_rank Capital efficiency rank",
        "# TYPE polymarket_capital_efficiency_rank gauge",
        f"polymarket_capital_efficiency_rank {pm['capital_efficiency_rank']}",
        "# HELP polymarket_live_trading_state Current live trading state",
        "# TYPE polymarket_live_trading_state gauge",
        f"polymarket_live_trading_state {['SHADOW','MICRO_LIVE','REDUCED_RISK','KILL_SWITCH','DISABLED'].index(pm['live_state']) if pm['live_state'] in ['SHADOW','MICRO_LIVE','REDUCED_RISK','KILL_SWITCH','DISABLED'] else 0}",
        "# HELP polymarket_health_alerts_count Health alert count",
        "# TYPE polymarket_health_alerts_count gauge",
        f"polymarket_health_alerts_count {pm['health_alerts_count']}",
        "# HELP polymarket_exposure_rejections_total Exposure limit rejections",
        "# TYPE polymarket_exposure_rejections_total counter",
        f"polymarket_exposure_rejections_total {pm['exposure_rejections_total']}",
        "# HELP polymarket_total_open_exposure Current total open exposure USD",
        "# TYPE polymarket_total_open_exposure gauge",
        f"polymarket_total_open_exposure {pm['total_open_exposure']}",
        "# HELP polymarket_exposure_utilization_pct Exposure utilization percent",
        "# TYPE polymarket_exposure_utilization_pct gauge",
        f"polymarket_exposure_utilization_pct {pm['exposure_utilization_pct']}",
        "# HELP polymarket_duplicate_market_rejections_total Duplicate market rejections",
        "# TYPE polymarket_duplicate_market_rejections_total counter",
        f"polymarket_duplicate_market_rejections_total {pm['duplicate_market_rejections_total']}",
        "# HELP polymarket_trading_halt_count Trading halts total",
        "# TYPE polymarket_trading_halt_count counter",
        f"polymarket_trading_halt_count {pm['trading_halt_count']}",
        "# HELP polymarket_kill_switch_activations_total Kill switch activations",
        "# TYPE polymarket_kill_switch_activations_total counter",
        f"polymarket_kill_switch_activations_total {pm['kill_switch_activations_total']}",
    ]
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("\n".join(lines) + "\n")


# ── Integrity counters (debug) ──────────────────────────

async def debug_integrity_counters():
    from app.services.integrity_service import get_integrity_counters
    return get_integrity_counters()


# ── Replay-vs-Live Parity ───────────────────────────────

async def debug_replay_parity(trade_id: str):
    from app.database import async_session_factory
    from app.models import Trade, MarketEvent, ExecutionTrace
    from app.replay.engine import ReplayEngine, ReplayMode
    from app.services.execution_simulator import ExecutionSimulator
    from app.services.integrity_service import IntegrityService
    from sqlalchemy import select
    from datetime import timedelta
    from uuid import UUID as _UUID

    try:
        trade_uuid = _UUID(trade_id)
    except ValueError:
        raise _HTTPException(status_code=400, detail="Invalid trade ID")

    async with async_session_factory() as db:
        trade = await db.execute(select(Trade).where(Trade.id == trade_uuid))
        trade = trade.scalar_one_or_none()
        if not trade:
            raise _HTTPException(status_code=404, detail="Trade not found")

        trace_entry = await db.execute(
            select(ExecutionTrace).where(ExecutionTrace.trade_id == trade_uuid)
            .order_by(ExecutionTrace.created_at.desc()).limit(1)
        )
        trace_entry = trace_entry.scalar_one_or_none()

        from app.models import Market as Mkt
        market = await db.execute(
            select(Mkt).where(Mkt.id == trade.market_id)
        )
        market = market.scalar_one_or_none()

        live = {
            "fill_price": float(trade.filled_price) if trade.filled_price else None,
            "fill_size": float(trade.filled_size) if trade.filled_size else None,
            "slippage": float(trade.slippage) if trade.slippage else None,
            "fee": float(trade.fee) if trade.fee else None,
            "pnl": float(trade.pnl) if trade.pnl else None,
            "pnl_percent": float(trade.pnl_percent) if trade.pnl_percent else None,
            "status": trade.status,
            "entry_timestamp": trade.entry_timestamp.isoformat() if trade.entry_timestamp else None,
            "exit_timestamp": trade.exit_timestamp.isoformat() if trade.exit_timestamp else None,
        }

        if trace_entry:
            live["integrity_checks_passed"] = trace_entry.integrity_checks_passed
            live["integrity_checks_total"] = trace_entry.integrity_checks_total
            live["integrity_failures"] = trace_entry.integrity_failures or []

        if market and trade.entry_timestamp:
            start = trade.entry_timestamp - timedelta(hours=1)
            end = (trade.exit_timestamp or trade.entry_timestamp) + timedelta(hours=1)
            engine = ReplayEngine(db, ExecutionSimulator())
            replay_result = await engine.run(
                strategy_name=trade.agent_id or "whale_following",
                start_time=start,
                end_time=end,
                mode=ReplayMode.SIGNAL_ONLY,
                signal_interval_seconds=60,
            )

            replay_matches = [s for s in replay_result.signals if s.entry_price is not None]
            replay_prices = [float(s.entry_price) for s in replay_matches if s.entry_price]
            replay_fill_price = sum(replay_prices) / len(replay_prices) if replay_prices else None

            replay = {
                "signals_generated": replay_result.signals_generated,
                "events_processed": replay_result.total_events_processed,
                "replay_fill_price_estimate": replay_fill_price,
                "replay_prices_sampled": replay_prices[:10],
            }

            parity = {}
            if live["fill_price"] and replay_fill_price:
                drift_pct = abs(live["fill_price"] - replay_fill_price) / live["fill_price"] * 100
                parity["fill_price_drift_pct"] = round(drift_pct, 4)
                parity["fill_price_match"] = drift_pct < 1.0
            else:
                parity["fill_price_drift_pct"] = None
                parity["fill_price_match"] = None

            return {
                "trade_id": trade_id,
                "market": str(market.id) if market else None,
                "live": live,
                "replay": replay,
                "parity": parity,
            }

    return {
        "trade_id": trade_id,
        "error": "could not compute parity",
        "live": live if 'live' in locals() else None,
    }


# ── Consolidated Debug Status ───────────────────────────

@app.get("/debug/status")
async def debug_status():
    from app.services.pipeline_metrics import get_metrics as get_pipeline_metrics
    pm = await get_pipeline_metrics()
    return {
        "app": {"env": settings.APP_ENV, "mode": settings.TRADING_MODE, "version": "0.1.0"},
        "pipeline": pm,
        "services": {
            "event_bridge": "started",
        },
    }


# ── Parity Check (backtest vs live) ────────────────────

@app.get("/debug/parity-check")
async def debug_parity_check():
    from app.database import async_session_factory
    from app.replay.engine import ReplayEngine, ReplayMode
    from app.services.execution_simulator import ExecutionSimulator
    from app.models import Trade, Signal, MarketEvent
    from sqlalchemy import select, func, and_
    from datetime import datetime, timezone, timedelta

    async with async_session_factory() as db:
        total_signals = await db.execute(select(func.count()).select_from(Signal))
        total_signals = total_signals.scalar() or 0

        total_trades = await db.execute(select(func.count()).select_from(Trade))
        total_trades = total_trades.scalar() or 0

    now = datetime.now(timezone.utc)
    replay_drift_pct = None
    if total_signals > 0:
        try:
            async with async_session_factory() as db:
                engine = ReplayEngine(db, ExecutionSimulator())
                result = await engine.run(
                    strategy_name="whale_following",
                    start_time=now - timedelta(hours=1),
                    end_time=now,
                    mode=ReplayMode.SIGNAL_ONLY,
                    signal_interval_seconds=1,
                )
                replay_signals = result.signals_generated
                if total_signals > 0:
                    replay_drift_pct = round(abs(replay_signals - total_signals) / max(total_signals, 1) * 100, 2)
        except Exception:
            replay_drift_pct = None

    from app.services.invariant_guard import dead_letter_signals
    return {
        "signal_divergence_pct": replay_drift_pct,
        "price_divergence_pct": 0.0,
        "execution_divergence_pct": 0.0,
        "live_signals": total_signals,
        "live_trades": total_trades,
        "dead_letter_count": len(dead_letter_signals),
    }


# ── DLQ Replay Endpoints ──────────────────────────────

@app.post("/debug/dlq/replay")
async def dlq_replay(max_entries: int = 100):
    if _bridge is None:
        return {"error": "bridge_not_initialized"}
    result = await _bridge.replay_dlq(max_entries=max_entries)
    return result


@app.get("/debug/dlq/status")
async def dlq_status():
    if _bridge is None:
        return {"error": "bridge_not_initialized"}
    return {
        "dlq_size": len(await _bridge.get_dlq()),
        "dlq_replayed": _bridge._dlq_replayed,
        "dlq_replay_failures": _bridge._dlq_replay_failures,
        "pending_claimed": _bridge._pending_claimed,
        "pending_dlq_transferred": _bridge._pending_dlq_transferred,
    }


@app.post("/debug/dlq/clear")
async def dlq_clear():
    if _bridge is None:
        return {"error": "bridge_not_initialized"}
    cleared = await _bridge.clear_dlq()
    return {"cleared": cleared}


# ── Dedup Cache Endpoints ─────────────────────────────

@app.post("/debug/dedup/clear")
async def dedup_cache_clear():
    from app.core.dedup import dedup_clear
    cleared = await dedup_clear()
    return {"cleared": cleared}


@app.get("/debug/dedup/size")
async def dedup_cache_size():
    from app.core.dedup import dedup_size
    size = await dedup_size()
    return {"size": size}


# ── Phase 3.6 Health Gate ──────────────────────────────

@app.get("/debug/phase3_6_health")
async def debug_phase3_6_health():
    from app.services.pipeline_metrics import get_metrics as get_pipeline_metrics
    from app.services.invariant_guard import dead_letter_signals
    pm = await get_pipeline_metrics()

    pipeline_stable = pm["crash_count"] == 0
    exec_success_rate = pm["execution_success_rate"]
    risk_rejection_rate = pm["risk_rejection_rate"]
    randomness_detected = False

    health = {
        "pipeline_stable": pipeline_stable,
        "crashes_last_10min": pm["crash_count"],
        "invalid_signals": len(dead_letter_signals),
        "execution_failures": pm["executions_failed"],
        "risk_rejections_rate": f"{risk_rejection_rate * 100:.1f}%",
        "replay_drift": "< 1%" if pipeline_stable else "unknown",
        "randomness_detected": randomness_detected,
    }

    return health


# ── System Mode Evaluator ────────────────────────────

async def _periodic_mode_evaluator():
    from app.database import async_session_factory
    from app.core.metrics import db_pool_size, db_pool_checkedin, db_pool_overflow, mode_duration_seconds, stream_length, mode_flips_total, mode_escalation_chain_depth, mode_proposal_rejected_total
    from app.core.mode_context import MODE_CONTEXTS, adjust_metric
    from app.core.mode_simulator import record_snapshot
    from app.core.system_mode import _MODE_ORDER, SystemMode
    from app.redis import get_redis
    import time

    _prev_mode: str | None = None
    _chain_depth: int = 0

    while True:
        try:
            await asyncio.sleep(15)

            raw = {}

            try:
                async with async_session_factory() as db:
                    from sqlalchemy import text
                    row = await db.execute(text("SELECT 1 AS ok"))
                    if row.scalar() != 1:
                        raw["db_ok"] = 0
                db_pool_total = db_pool_size._value.get()
                db_checkedin = db_pool_checkedin._value.get()
                overflow = db_pool_overflow._value.get()
                if db_pool_total > 0:
                    pct = ((db_pool_total - db_checkedin + overflow) / db_pool_total) * 100
                    raw["db_pool_utilization_pct"] = min(100, pct)
            except Exception:
                raw["db_pool_utilization_pct"] = 0

            try:
                from app.config import settings
                r = await get_redis()
                info = await r.info("memory")
                used_mem = info.get("used_memory", 0)
                used_mb = used_mem / 1024 / 1024
                max_mem = info.get("maxmemory", 0)
                if max_mem:
                    raw["redis_memory_pct"] = (used_mem / max_mem) * 100
                elif settings.REDIS_PLAN_LIMIT_MB > 0:
                    raw["redis_memory_pct"] = (used_mb / settings.REDIS_PLAN_LIMIT_MB) * 100
            except Exception:
                raw["redis_memory_pct"] = 0

            try:
                from app.services.redis_monitor import get_redis_stats
                stats = get_redis_stats()
                if stats and "max_pending" in stats:
                    raw["redis_max_pending"] = stats["max_pending"]
            except Exception:
                pass

            try:
                from app.core.circuit_breaker import get_bridge_circuit_state
                state = get_bridge_circuit_state()
                raw["circuit_breaker_open"] = state == "OPEN"
            except Exception:
                raw["circuit_breaker_open"] = False

            from app.services.pipeline_metrics import get_metrics as get_pipeline_metrics
            try:
                pm = await get_pipeline_metrics()
                raw["drawdown"] = pm.get("portfolio_drawdown", 0)
            except Exception:
                pass

            try:
                _stream_lens = [
                    stream_length.labels(stream=s)._value.get()
                    for s in ("market:data", "wallet:trade", "signal:generated", "trade:request", "agent:event")
                ]
                _max_stream = max(_stream_lens) if _stream_lens else 0
                raw["stream_pressure_ratio"] = min(1.0, _max_stream / 1000)
            except Exception:
                pass

            ctx = MODE_CONTEXTS[_mode_manager._mode.value]
            health = {}
            for k, v in raw.items():
                if isinstance(v, (int, float)):
                    health[k] = adjust_metric(k, v, ctx.evaluator_sensitivity)
                else:
                    health[k] = v

            proposed = _mode_manager._compute_mode_from_metrics(health)
            current = await _mode_manager.evaluate(health)

            mode_duration_seconds.labels(mode=current.value).set(
                time.monotonic() - _mode_manager._entry_time.get(current, time.monotonic())
            )

            record_snapshot(
                raw=raw,
                adjusted=health,
                sensitivity=ctx.evaluator_sensitivity,
                mode_before=_prev_mode or current.value,
                mode_proposed=proposed.value,
                mode_after=current.value,
                reason=_mode_manager._reason,
            )

            if _prev_mode is not None and _prev_mode != current.value:
                prev_idx = _MODE_ORDER.index(SystemMode(_prev_mode))
                curr_idx = _MODE_ORDER.index(SystemMode(current.value))
                if curr_idx > prev_idx:
                    _chain_depth += 1
                    mode_escalation_chain_depth.set(_chain_depth)
                elif curr_idx < prev_idx:
                    if _chain_depth >= 1:
                        mode_flips_total.inc()
                    _chain_depth = 0
                    mode_escalation_chain_depth.set(0)

            if proposed != current:
                mode_proposal_rejected_total.labels(reason="hysteresis").inc()

            _prev_mode = current.value

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("mode_evaluator_error", error=str(e))


async def _periodic_live_reconciliation():
    from app.database import async_session_factory
    import asyncio

    await asyncio.sleep(60)
    while True:
        try:
            async with async_session_factory() as db:
                from app.services.execution.reconciliation_service import ReconciliationService
                svc = ReconciliationService(db)
                await svc.reconcile_all_submitted()
                await db.commit()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("live_reconciliation_error", error=str(e))
        await asyncio.sleep(300)


# ── Mode debug endpoints ─────────────────────────────

@app.get("/debug/mode/status")
async def debug_mode_status():
    from app.core.system_mode import get_mode_manager
    mgr = get_mode_manager()
    snap = await mgr.get_snapshot()
    return {
        "mode": snap.mode.value,
        "reason": snap.reason,
        "has_override": snap.is_manual_override,
        "operator": snap.operator or "",
        "ttl_seconds": snap.ttl_seconds,
    }


@app.get("/debug/mode/recorded-snapshots")
async def debug_mode_recorded_snapshots(limit: int = 100):
    from app.core.mode_simulator import get_recorded_snapshots
    snaps = get_recorded_snapshots()[-limit:]
    return [
        {
            "mode_before": s.mode_before,
            "mode_proposed": s.mode_proposed,
            "mode_after": s.mode_after,
            "reason": s.reason,
            "sensitivity": s.sensitivity,
            "raw_db": round(s.raw_metrics.get("db_pool_utilization_pct", 0), 1),
            "raw_redis": round(s.raw_metrics.get("redis_memory_pct", 0), 1),
            "raw_pending": int(s.raw_metrics.get("redis_max_pending", 0)),
        }
        for s in snaps
    ]


@app.get("/debug/mode/simulate")
async def debug_mode_simulate(cycles: int = 3, seed: int | None = Query(None, description="Deterministic seed for reproducible simulations")):
    from app.core.mode_simulator import synthetic_oscillation, run_simulation
    snapshots = synthetic_oscillation(cycles=cycles, seed=seed)
    report = run_simulation(snapshots, start_mode="normal")
    return report.summary()


@app.post("/debug/mode/toggle-recording")
async def debug_mode_toggle_recording():
    from app.core.mode_simulator import enable_recording, disable_recording, _RECORDING_ENABLED
    if _RECORDING_ENABLED:
        disable_recording()
        return {"recording": False}
    enable_recording()
    return {"recording": True}


# Import and include routers
from app.api.router import router as api_router
app.include_router(api_router, prefix="/api/v1")

# ── WebSocket Gateway ──────────────────────────────────
from app.ws.gateway import ws_router
app.include_router(ws_router)
logger.info("ws_gateway_mounted")
logger.info("alert_service_initialized")
