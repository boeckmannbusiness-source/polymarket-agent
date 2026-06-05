from prometheus_client import Counter, Histogram, Gauge

_FAST_BUCKETS = [1, 5, 10, 25, 50, 100, 250]
_MEDIUM_BUCKETS = [10, 25, 50, 100, 250, 500, 1000, 5000]
_SLOW_BUCKETS = [100, 500, 1000, 5000, 10000, 30000, 60000]
_E2E_BUCKETS = [100, 500, 1000, 5000, 10000, 30000, 60000, 300000]

signals_total = Counter("polymarket_signals_generated_total", "Total signals generated", ["strategy"])
executions_total = Counter("polymarket_trades_executed_total", "Total trades executed", ["strategy", "outcome"])
execution_failures_total = Counter("polymarket_trade_failures_total", "Trade failures", ["reason"])
risk_rejections_total = Counter("polymarket_risk_rejections_total", "Risk rejections", ["reason"])
crashes_total = Counter("polymarket_crashes_total", "Unexpected crashes")
integrity_failures_total = Counter("polymarket_integrity_failures_total", "Integrity assertion failures")
trace_persist_failures_total = Counter("polymarket_trace_persist_failures_total", "Trace persistence failures")
pending_trade_timeouts_total = Counter("polymarket_pending_trade_timeouts_total", "Pending trade timeouts")
duplicate_market_rejections_total = Counter("polymarket_duplicate_market_rejections_total", "Duplicate market rejections")
recovery_loop_errors_total = Counter("polymarket_recovery_loop_errors_total", "Recovery loop failures", ["loop_name"])
recovery_loop_recoveries_total = Counter("polymarket_recovery_loop_recoveries_total", "Messages recovered", ["loop_name"])
dlq_replay_success_total = Counter("polymarket_dlq_replay_total", "Successful DLQ replays", ["origin_stream"])
dlq_replay_failures_total = Counter("polymarket_dlq_replay_failures_total", "Failed DLQ replays", ["origin_stream"])
telegram_send_failures_total = Counter("polymarket_telegram_send_failures_total", "Telegram send failures")

recovery_scans_total = Counter("polymarket_recovery_scans_total", "Order recovery scans performed")
recovered_orders_total = Counter("polymarket_recovered_orders_total", "Orders recovered by recovery service")
abandoned_orders_total = Counter("polymarket_abandoned_orders_total", "Orders marked abandoned by recovery")
scheduler_job_failures_total = Counter("polymarket_scheduler_job_failures_total", "Scheduler job failures", ["job_name"])
scheduler_execution_duration = Histogram("polymarket_scheduler_execution_duration_seconds", "Scheduler job execution duration", buckets=_MEDIUM_BUCKETS, labelnames=["job_name"])

stream_length = Gauge("polymarket_stream_length", "Redis stream length", ["stream"])
consumer_pending = Gauge("polymarket_consumer_pending", "Pending messages per consumer group", ["stream", "consumer_group"])
redis_memory_usage_mb = Gauge("polymarket_redis_memory_usage_mb", "Redis used memory in MB")
redis_aof_enabled = Gauge("polymarket_redis_aof_enabled", "Redis AOF persistence enabled (1 or 0)")
dedup_key_count = Gauge("polymarket_dedup_key_count", "Dedup key count")
redis_keys_total = Gauge("polymarket_redis_keys_total", "Total Redis keys across all databases")
redis_peak_memory_mb = Gauge("polymarket_redis_peak_memory_mb", "Redis peak memory in MB")
redis_utilization_pct = Gauge("polymarket_redis_utilization_pct", "Redis maxmemory utilization percentage")
redis_provider_utilization_pct = Gauge("polymarket_redis_provider_utilization_pct", "Redis provider plan utilization percentage (used_memory / REDIS_PLAN_LIMIT_MB)")
stream_trim_count = Gauge("polymarket_stream_trimmed_messages", "Messages trimmed from stream", ["stream"])
db_pool_size = Gauge("polymarket_db_pool_size", "DB connection pool state", ["state"])
pel_depth = Gauge("polymarket_pel_depth", "XPENDING depth by stream:group", ["stream", "group"])
dlq_size = Gauge("polymarket_dlq_size", "DLQ size across all streams", ["origin_stream"])
recovery_stuck_count = Gauge("polymarket_recovery_stuck_count", "Stuck items in recovery", ["loop_name"])
replay_drift_pct = Gauge("polymarket_replay_drift_percent", "Replay vs live signal count drift", ["strategy"])
replay_deterministic = Gauge("polymarket_replay_deterministic", "Replay determinism status", ["strategy"])

ws_ingest_latency = Histogram("polymarket_ws_ingest_latency_ms", "WS ingest latency", buckets=_FAST_BUCKETS)
signal_generation_latency = Histogram("polymarket_signal_generation_latency_ms", "Signal generation latency", buckets=_MEDIUM_BUCKETS, labelnames=["strategy"])
risk_evaluation_latency = Histogram("polymarket_risk_evaluation_latency_ms", "Risk evaluation latency", buckets=_MEDIUM_BUCKETS)
execution_latency = Histogram("polymarket_execution_latency_ms", "Trade execution latency", buckets=_MEDIUM_BUCKETS)
persistence_latency = Histogram("polymarket_persistence_latency_ms", "Market event persistence latency", buckets=_FAST_BUCKETS)
allocation_latency = Histogram("polymarket_allocation_latency_ms", "Portfolio allocation latency", buckets=_FAST_BUCKETS)
db_query_latency = Histogram("polymarket_db_query_latency_ms", "DB query latency", buckets=_FAST_BUCKETS, labelnames=["query_type"])
end_to_end_latency = Histogram("polymarket_trade_e2e_latency_ms", "End-to-end trade latency", buckets=_E2E_BUCKETS)
event_to_execution_latency = Histogram("polymarket_event_to_execution_latency_ms", "Market event → execution decision latency", buckets=_E2E_BUCKETS)

system_mode_gauge = Gauge("polymarket_system_mode", "Current system mode (1 if active)", ["mode"])
mode_transitions_total = Counter("polymarket_mode_transitions_total", "Mode transitions", ["from_mode", "to_mode"])
mode_override_active = Gauge("polymarket_mode_override_active", "Manual override is active (1 or 0)")
mode_duration_seconds = Gauge("polymarket_mode_duration_seconds", "Duration in current mode", ["mode"])
metric_classification_unknown_total = Counter("polymarket_metric_classification_unknown_total", "Unclassified metrics encountered", ["metric_name"])
mode_flips_total = Counter("polymarket_mode_flips_total", "Mode direction flips within oscillation window")
mode_escalation_chain_depth = Gauge("polymarket_mode_escalation_chain_depth", "Current escalation chain length")
mode_proposal_rejected_total = Counter("polymarket_mode_proposal_rejected_total", "Proposed mode rejections", ["reason"])

# ── Phase 4E Intelligence metrics ──────────────────────────
portfolio_reviews_generated = Counter("polymarket_portfolio_reviews_generated_total", "Portfolio reviews generated")
committee_reports_generated = Counter("polymarket_committee_reports_generated_total", "Committee reports generated")
stress_tests_executed = Counter("polymarket_stress_tests_executed_total", "Stress tests executed")
regime_allocations_generated = Counter("polymarket_regime_allocations_generated_total", "Regime allocations generated")
resilience_reports_generated = Counter("polymarket_resilience_reports_generated_total", "Resilience reports generated")

# ── Phase 4F Optimization metrics ──────────────────────────
portfolio_optimization_runs = Counter("polymarket_portfolio_optimization_runs_total", "Total portfolio optimization runs")
monte_carlo_simulations_executed = Counter("polymarket_monte_carlo_simulations_total", "Monte Carlo simulations executed")
allocation_learning_updates = Counter("polymarket_allocation_learning_updates_total", "Allocation learning updates applied")
risk_model_updates = Counter("polymarket_risk_model_updates_total", "Risk model recalculations")

# ── Phase 4G Control metrics ──────────────────────────
portfolio_stability_score = Gauge("polymarket_portfolio_stability_score", "Portfolio stability score (0-100)")
allocation_drift_events = Counter("polymarket_allocation_drift_events_total", "Allocation drift events detected")
feedback_dampening_adjustments = Counter("polymarket_feedback_dampening_adjustments_total", "Feedback dampening adjustments applied")
regime_stability_updates = Counter("polymarket_regime_stability_updates_total", "Regime stability updates applied")
